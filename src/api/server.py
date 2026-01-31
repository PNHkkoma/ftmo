
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import time
import MetaTrader5 as mt5
from typing import List

from ..config import DEFAULT_SYMBOLS, TIMEFRAME, ACCOUNT_SIZE, MAX_TOTAL_LOSS, SAFE_DAILY_BUFFER
from ..core.mt5_interface import mt5_connector
from ..core.strategy import calculate_indicators, analyze_market_structure
from ..core.ai_adviser import AIAdviser

app = FastAPI(title="FTMO Pro Trader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State
market_state = {}
active_symbols = DEFAULT_SYMBOLS.copy()
ai_agent = AIAdviser()

class TradeRequest(BaseModel):
    symbol: str
    action: str  # BUY, SELL, BUY_LIMIT, SELL_LIMIT
    volume: float
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0

ORDER_TYPE_MAP = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
}

@app.on_event("startup")
def startup_event():
    mt5_connector.connect()
    # Start background data loop
    t = threading.Thread(target=data_loop, daemon=True)
    t.start()

def data_loop():
    while True:
        try:
            for sym in active_symbols:
                try:
                    # Get Data
                    df = mt5_connector.get_rates(sym, TIMEFRAME, n=100)
                    if df is not None:
                        df = calculate_indicators(df)
                        analysis = analyze_market_structure(df)
                        
                        # Add current live bid/ask if possible
                        bid, ask = mt5_connector.get_current_price(sym)
                        analysis["bid"] = bid
                        analysis["ask"] = ask
                        
                        # Update State
                        market_state[sym] = analysis
                except Exception as e:
                    print(f"Error updating {sym}: {e}")
        except Exception as outer_e:
            print(f"Loop error: {outer_e}")
            
        time.sleep(1)

@app.get("/api/status")
def get_status():
    account = mt5_connector.get_account_info()
    return {
        "connected": mt5_connector.connected,
        "balance": account.balance if account else 0,
        "equity": account.equity if account else 0,
        "symbols_tracked": len(active_symbols),
        "tracked_list": active_symbols
    }

@app.get("/api/market_data")
def get_market_data():
    return market_state

@app.post("/api/analyze/{symbol}")
def analyze_symbol(symbol: str):
    if symbol not in market_state:
        raise HTTPException(status_code=404, detail="Symbol not tracked or no data")
    
    analysis = ai_agent.analyze(symbol, market_state[symbol])
    return analysis

@app.post("/api/trade")
def execute_trade(trade: TradeRequest):
    # FTMO Guard
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
    
    # Auto-fill current price for market orders if 0
    price_to_use = trade.price
    if mt5_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
        # Market execution usually ignores price in Python MT5 bindings if using DEAL, 
        # but good to be explicit or let MT5 handle it. 
        # Actually in order_send for market, price should be current Ask/Bid.
        bid, ask = mt5_connector.get_current_price(trade.symbol)
        if mt5_type == mt5.ORDER_TYPE_BUY:
            price_to_use = ask
        else:
            price_to_use = bid

    res = mt5_connector.place_order(
        trade.symbol, 
        mt5_type,
        trade.volume,
        price_to_use,
        trade.sl,
        trade.tp
    )
    return res

@app.post("/api/symbols")
def add_symbol(symbol: str):
    symbol = symbol.upper()
    if not mt5_connector.check_symbol(symbol):
        raise HTTPException(status_code=400, detail="Symbol Invalid in MT5")
    if symbol not in active_symbols:
        active_symbols.append(symbol)
    return {"status": "added", "symbol": symbol}

# Mount static files (Frontend)
import os
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
