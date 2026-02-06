
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import time
import asyncio
import json
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from typing import List

from ..config import DEFAULT_SYMBOLS, TIMEFRAME, ACCOUNT_SIZE, MAX_TOTAL_LOSS, SAFE_DAILY_BUFFER
from ..core.mt5_interface import mt5_connector
from ..core.strategy import calculate_indicators, analyze_market_structure
from ..core.ai_adviser import AIAdviser
from .models import TradeRequest

app = FastAPI(title="FTMO Pro Trader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        try:
            to_send = json.dumps(message, default=str)
        except Exception as e:
            print(f"JSON Dump Error: {e} - Msg: {message}")
            return
            
        for connection in self.active_connections:
            try:
                await connection.send_text(to_send)
            except Exception as e:
                # print(f"WS Send Error: {e}") 
                pass

manager = ConnectionManager()

# State
market_state = {}
active_symbols = DEFAULT_SYMBOLS.copy()
ai_agent = AIAdviser()
all_mt5_symbols = [] 



ORDER_TYPE_MAP = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
}

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

@app.on_event("startup")
def startup_event():
    mt5_connector.connect()
    refresh_symbol_cache()
    # Start background data loop
    t = threading.Thread(target=run_async_data_loop, daemon=True)
    t.start()

def refresh_symbol_cache():
    global all_mt5_symbols
    if mt5_connector.connect():
        symbols = mt5.symbols_get()
        if symbols:
            all_mt5_symbols = [s.name for s in symbols]

from ..core.telegram_bot import send_telegram_message

def run_async_data_loop():
    """Helper to run async loop in thread"""
    asyncio.run(main_loops())

async def main_loops():
    await asyncio.gather(data_loop(), telegram_scheduler())

async def telegram_scheduler():
    print("📱 Telegram Scheduler Started...")
    while True:
        try:
            # 30 Minutes Interval = 1800 seconds
            await asyncio.sleep(600)
            if "XAUUSD" in market_state:
                # Analyze
                analysis = ai_agent.analyze("XAUUSD", market_state["XAUUSD"])
                print(market_state["XAUUSD"])
                # Flatten manually if needed (server analyze_symbol does this too, but here we call raw analyze)
                if "execution" in analysis and isinstance(analysis["execution"], dict):
                     exe = analysis["execution"]
                     if exe.get("entry"): analysis["entry"] = exe.get("entry")
                     if exe.get("sl"): analysis["sl"] = exe.get("sl")
                     if exe.get("tp"): analysis["tp"] = exe.get("tp")

                # Format Message
                action = analysis.get("action", "WAIT")
                
                msg = ""
                if action in ["BUY", "SELL"]:
                    msg = f"🚨 **SIGNAL DETECTED** 🚨\n\n"
                    msg += f"Symbol: XAUUSD\n"
                    msg += f"Action: *{action}* ({analysis.get('setup_quality', 'N/A')})\n"
                    msg += f"Entry: {analysis.get('entry', 'Market')}\n"
                    msg += f"SL: {analysis.get('sl')}\nTP: {analysis.get('tp')}\n\n"
                    msg += f"Reason: _{analysis.get('professional_rationale', 'N/A')}_"
                else:
                    # WAIT message (Full Detail)
                    msg = f"⏳ **AI STATUS: WAIT**\n"
                    reasons = analysis.get("wait_reasons", [])
                    if reasons:
                        # Join all reasons with a bullet point
                        formatted_reasons = "\n".join([f"• {r}" for r in reasons])
                        msg += f"\n{formatted_reasons}"
                    
                    # Add rationale if available
                    if analysis.get("professional_rationale"):
                        msg += f"\n\n_Note: {analysis.get('professional_rationale')}_"
                
                await send_telegram_message(msg)

        except Exception as e:
            print(f"Tele Loop Error: {e}")

async def data_loop():
    while True:
        try:
            updates = {}
            for sym in active_symbols:
                try:
                    # Optimize: Get tick only for speed first? No, we need OHLC for strategy
                    # Using get_rates is relatively 'slow' (ms), but necessary for indicators
                    # Increase buffer to 300 to support extended FVG lookback
                    df = mt5_connector.get_rates(sym, TIMEFRAME, n=300)
                    df_h1 = mt5_connector.get_rates(sym, mt5.TIMEFRAME_H1, n=300)

                    if df is not None:
                        df = calculate_indicators(df)
                        analysis = analyze_market_structure(df, timeframe_label="M5")

                        # HTF Analysis
                        htf_bias = "Neutral"
                        if df_h1 is not None:
                             df_h1 = calculate_indicators(df_h1)
                             st_h1 = analyze_market_structure(df_h1, timeframe_label="H1")
                             htf_bias = st_h1.get("bias", "Neutral")
                        
                        analysis["htf_bias"] = htf_bias
                        analysis["ltf_bias"] = analysis.get("bias", "Neutral")
                        
                        # Session Analysis (UTC Base)
                        # SVT (Server Time) is usually EET (UTC+2 or +3)
                        # Best way is to map UTC.
                        try:
                            # Current UTC Time
                            utc_now = datetime.utcnow()
                            h = utc_now.hour
                            
                            # Forex Sessions (Approx UTC)
                            # Sydney: 22:00 - 07:00
                            # Tokyo: 00:00 - 09:00
                            # London: 08:00 - 17:00 (Pre-open 07:00)
                            # New York: 13:00 - 22:00
                            
                            sess = "Pacific/Asia"
                            if 7 <= h < 13: sess = "London (Morning)"
                            elif 13 <= h < 17: sess = "London/NY Overlap"
                            elif 17 <= h < 22: sess = "New York (Late)"
                            
                            analysis["session"] = sess
                        except:
                            analysis["session"] = "Unknown"
                            
                        analysis["dxy_bias"] = "Neutral"
                        analysis["news_event"] = "No Data" # Explicitly tell AI we have no news feed
                        
                        bid, ask = mt5_connector.get_current_price(sym)
                        analysis["bid"] = bid
                        analysis["ask"] = ask
                        analysis["time"] = datetime.now().timestamp()
                        analysis["symbol"] = sym 
                        
                        market_state[sym] = analysis
                        updates[sym] = analysis
                except Exception as e:
                    print(f"Error updating {sym}: {e}")
            
            # Broadcast updates via WebSocket
            if updates:
                await manager.broadcast({"type": "MARKET_DATA", "data": updates})
            
            # Broadcast Server Time
            server_time = mt5_connector.get_server_time()
            account = mt5_connector.get_account_info()
            # Broadcast Positions (Fetch fresh every 0.5s is fine for local)
            positions = mt5_connector.get_positions()
            if positions is not None:
                await manager.broadcast({"type": "POSITIONS", "data": positions})

            status_update = {
                "type": "STATUS",
                "data": {
                    "connected": mt5_connector.connected,
                    "broker_time_str": server_time.strftime("%H:%M:%S"),
                    "balance": account.balance if account else 0,
                    "equity": account.equity if account else 0
                }
            }
            await manager.broadcast(status_update)

        except Exception as outer_e:
            print(f"Loop error: {outer_e}")
            
        await asyncio.sleep(0.5) # Fast polling (500ms)

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive, listen for pings if any
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- REST Endpoints ---
@app.get("/api/status")
def get_status():
    account = mt5_connector.get_account_info()
    broker_time = mt5_connector.get_server_time()
    return {
        "connected": mt5_connector.connected,
        "balance": account.balance if account else 0,
        "equity": account.equity if account else 0,
        "profit": account.profit if account else 0,
        "broker_time_str": broker_time.strftime("%H:%M:%S"),
        "broker_time_ts": broker_time.timestamp()
    }

@app.get("/api/market_data")
def get_market_data():
    return market_state

@app.get("/api/chart_data")
def get_chart_data(symbol: str, timeframe: str = "M5"):
    tf = TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M5)
    df = mt5_connector.get_rates(symbol, tf, n=500)
    if df is None: return []
    
    results = []
    for _, row in df.iterrows():
        results.append({
            "time": int(row['time'].timestamp()),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close']
        })
    return results

@app.get("/api/history")
def get_history(days: int = 30):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    deals = mt5_connector.get_deals_history(from_date, to_date)
    return deals

@app.get("/api/search_symbols")
def search_symbols(q: str = Query(..., min_length=1)):
    q = q.upper()
    results = [s for s in all_mt5_symbols if q in s]
    return results[:10]

@app.post("/api/analyze/{symbol}")
def analyze_symbol(symbol: str):
    if symbol not in market_state:
        raise HTTPException(status_code=404, detail="Symbol not tracked or no data")
    # 1. Get AI Analysis
    analysis = ai_agent.analyze(symbol, market_state[symbol])

    # 1.5 Flatten Execution
    if "execution" in analysis and isinstance(analysis["execution"], dict):
        exe = analysis["execution"]
        if exe.get("entry"): analysis["entry"] = exe.get("entry")
        if exe.get("sl"): analysis["sl"] = exe.get("sl")
        if exe.get("tp"): analysis["tp"] = exe.get("tp")
    
    # 2. Logic Layer: Auto-Calculate Volume (Risk Management)
    if analysis.get("action") not in ["WAIT", "ERROR"] and analysis.get("sl"):
        try:
            # A. Account Risk (1% Default - User Configurable later)
            account = mt5_connector.get_account_info()
            if account:
                balance = account.balance
                risk_per_trade = balance * 0.01 # 1% Risk
                
                # B. Symbol Details for Pip Value
                info = mt5.symbol_info(symbol)
                if info:
                    # C. Determine Entry Price
                    entry = analysis.get("entry")
                    if not entry: # If Market Order, AI might send null
                        # Use current Ask for Buy, Bid for Sell as approximation
                        bid, ask = mt5_connector.get_current_price(symbol)
                        if "BUY" in analysis["action"]:
                            entry = ask
                        else:
                            entry = bid
                        
                        # Update entry in analysis for UI pre-fill
                        analysis["entry"] = entry
                    
                    # D. Calculate Distance
                    dist = abs(entry - float(analysis["sl"]))
                    
                    if dist > 0:
                        # Formula: Risk / (PriceDist * (TickValue / TickSize))
                        # TickValue is the value of 1 lot for 1 tick change
                        # Standard Forex: TickSize=0.00001, TickValue=1 (USD) -> 1 pip = $10/lot
                        # XAUUSD: TickSize=0.01, TickValue=1 -> 1$ move = $100/lot
                        
                        tick_size = info.trade_tick_size
                        tick_value = info.trade_tick_value
                        
                        if tick_size > 0 and tick_value > 0:
                            loss_per_lot = (dist / tick_size) * tick_value
                            raw_volume = risk_per_trade / loss_per_lot
                            
                            # E. Rounding to Lot Step
                            step = info.volume_step
                            # Round to nearest step
                            suggested_vol = round(raw_volume / step) * step
                            # Min/Max Check
                            suggested_vol = max(info.volume_min, min(suggested_vol, info.volume_max))
                            
                            analysis["suggested_volume"] = round(suggested_vol, 2)
                            analysis["risk_calc"] = f"Risk ${int(risk_per_trade)} ({round(raw_volume,2)} lots)"
                            
        except Exception as e:
            print(f"Volume calc error: {e}")
            analysis["suggested_volume"] = 0.01 # Fallback
            
    return analysis

@app.post("/api/trade")
def execute_trade(trade: TradeRequest):
    account = mt5_connector.get_account_info()
    if account:
        daily_dd = account.balance - account.equity
        if daily_dd > SAFE_DAILY_BUFFER:
             raise HTTPException(status_code=400, detail=f"FTMO DAILY BUFFER EXCEEDED (DD: {daily_dd})")
        if account.equity < (ACCOUNT_SIZE - MAX_TOTAL_LOSS):
             raise HTTPException(status_code=400, detail="FTMO MAX LOSS HIT")

    if trade.action not in ORDER_TYPE_MAP:
        raise HTTPException(status_code=400, detail="Invalid Order Type")
        
    mt5_type = ORDER_TYPE_MAP[trade.action]
    price_to_use = trade.price
    if mt5_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
        bid, ask = mt5_connector.get_current_price(trade.symbol)
        if mt5_type == mt5.ORDER_TYPE_BUY:
            price_to_use = ask
        else:
            price_to_use = bid

    res = mt5_connector.place_order(trade.symbol, mt5_type, trade.volume, price_to_use, trade.sl, trade.tp)
    return res

@app.post("/api/symbols")
def add_symbol(symbol: str):
    symbol = symbol.upper()
    if not mt5_connector.check_symbol(symbol):
        raise HTTPException(status_code=400, detail="Symbol Invalid in MT5")
    if symbol not in active_symbols:
        active_symbols.append(symbol)
    return {"status": "added", "symbol": symbol}

from .models import TradeRequest, PositionModifyRequest, PositionCloseRequest

@app.get("/api/positions")
def get_positions():
    return mt5_connector.get_positions()

@app.post("/api/positions/close")
def close_position(req: PositionCloseRequest):
    res = mt5_connector.close_position(req.ticket)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.post("/api/positions/modify")
def modify_position(req: PositionModifyRequest):
    res = mt5_connector.modify_position(req.ticket, req.sl, req.tp)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.get("/api/orders/history")
def get_orders_history(days: int = 30):
    from datetime import datetime, timedelta
    start = datetime.now() - timedelta(days=days)
    return mt5_connector.get_history_orders(from_date=start)

@app.get("/api/debug_mt5")
def debug_mt5():
    import MetaTrader5 as mt5
    connected = mt5_connector.connect()
    term_info = mt5.terminal_info()
    account_info = mt5.account_info()
    
    # Check RAW
    raw_pos = mt5.positions_get()
    raw_orders = mt5.orders_get()
    
    return {
        "connected": connected,
        "terminal": term_info._asdict() if term_info else None,
        "account": account_info._asdict() if account_info else None,
        "raw_positions_count": len(raw_pos) if raw_pos else 0,
        "raw_orders_count": len(raw_orders) if raw_orders else 0,
        "last_error": mt5.last_error()
    }

import os
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
