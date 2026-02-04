
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MT5_Interface")

class MT5Connector:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MT5Connector, cls).__new__(cls)
            cls._instance.connected = False
        return cls._instance

    def connect(self):
        if not self.connected:
            # CRITICAL: Do NOT use path parameter - it creates a new instance!
            # Instead, let MT5 auto-connect to the running terminal
            res = mt5.initialize()
            
            if not res:
                logger.error(f"Initialize failed, error code = {mt5.last_error()}")
                return False
            
            self.connected = True
            term_info = mt5.terminal_info()
            account_info = mt5.account_info()
            logger.info(f"MT5 Connected. Data Path: {term_info.data_path}")
            logger.info(f"MT5 Account: {account_info.login if account_info else 'Unknown'}")
        return True

    def get_account_info(self):
        if not self.connect(): return None
        return mt5.account_info()

    def get_server_time(self):
        if not self.connect(): return datetime.now()
        # mt5 doesn't have a direct "get_server_time" that returns a localized object easily without tick
        # But we can get the last tick time of a major pair
        tick = mt5.symbol_info_tick("EURUSD")
        if tick:
            return datetime.fromtimestamp(tick.time)
        return datetime.now()

    def get_rates(self, symbol, timeframe=mt5.TIMEFRAME_M5, n=100):
        if not self.connect(): return None
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None or len(rates) == 0:
            logger.warning(f"No rates for {symbol}")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_current_price(self, symbol):
        if not self.connect(): return None
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return tick.bid, tick.ask

    def check_symbol(self, symbol):
        if not self.connect(): return False
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            logger.error(f"Failed to select {symbol}")
            return False
        return True

    def place_order(self, symbol, order_type, volume, price, sl, tp, comment="FTMO_AI_Bot"):
        if not self.connect(): return None
        
        # 1. Normalize Price/SL/TP to tick size
        info = mt5.symbol_info(symbol)
        if not info:
            return {"status": "error", "message": "Symbol not found"}
        
        point = info.point
        digits = info.digits
        
        price = float(price)
        sl = float(sl)
        tp = float(tp)
        
        # Rounding strictly to digits
        price = round(price, digits)
        if sl > 0: sl = round(sl, digits)
        if tp > 0: tp = round(tp, digits)

        # Determine correct filling mode
        filling_type = mt5.ORDER_FILLING_IOC
        
        # Pending orders generally use RETURN (GTC)
        if order_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP]:
            filling_type = mt5.ORDER_FILLING_RETURN
            action_type = mt5.TRADE_ACTION_PENDING
        else:
            action_type = mt5.TRADE_ACTION_DEAL

        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        result = mt5.order_send(request)
        
        # Fallback for Market Orders if IOC fails
        if result.retcode == 10030 and action_type == mt5.TRADE_ACTION_DEAL:
            request["type_filling"] = mt5.ORDER_FILLING_RETURN
            result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.retcode} - {result.comment}")
            msg = result.comment
            if result.retcode == 10027:
                msg = "AutoTrading bị tắt trên MT5. Vui lòng bật nút 'Algo Trading' trên phần mềm MetaTrader 5."
            return {"status": "error", "message": msg}
        
        logger.info(f"Order placed: {result}")
        return {"status": "success", "ticket": result.order}

    def get_positions(self):
        if not self.connect(): return []
        
        data = []
        
        # Get active positions
        positions = mt5.positions_get()
        
        # Fallback: try with group filter if empty
        if positions is None or len(positions) == 0:
             positions = mt5.positions_get(group="*")

        if positions:
            for p in positions:
                data.append({
                    "ticket": int(p.ticket),
                    "symbol": str(p.symbol),
                    "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": float(p.volume),
                    "price_open": float(p.price_open),
                    "price_current": float(p.price_current),
                    "sl": float(p.sl),
                    "tp": float(p.tp),
                    "profit": float(p.profit),
                    "time": int(p.time),
                    "status": "OPEN"
                })

        # Get pending orders
        orders = mt5.orders_get()
        if orders:
            for o in orders:
                # Map MT5 Order Types to String
                o_type = "UNKNOWN"
                if o.type == mt5.ORDER_TYPE_BUY_LIMIT: o_type = "BUY_LIMIT"
                elif o.type == mt5.ORDER_TYPE_SELL_LIMIT: o_type = "SELL_LIMIT"
                elif o.type == mt5.ORDER_TYPE_BUY_STOP: o_type = "BUY_STOP"
                elif o.type == mt5.ORDER_TYPE_SELL_STOP: o_type = "SELL_STOP"
                
                data.append({
                    "ticket": int(o.ticket),
                    "symbol": str(o.symbol),
                    "type": str(o_type),
                    "volume": float(o.volume_current),
                    "price_open": float(o.price_open),
                    "price_current": float(o.price_current), 
                    "sl": float(o.sl),
                    "tp": float(o.tp),
                    "profit": 0.0,
                    "time": int(o.time_setup),
                    "status": "PENDING"
                })
                
        return data

    def get_history_orders(self, from_date=None, to_date=None):
        if not self.connect(): return []
        
        if from_date is None:
            # Default to 30 days ago to ensure we see recent activity
            from_date = datetime.now() - timedelta(days=30)
        if to_date is None:
            to_date = datetime.now() + timedelta(days=1)

        # Retrieve history orders. 
        # Note: If group="*" is used, it fetches all. If omitted, it depends on MT5 settings or fetches all.
        # Let's try WITHOUT group first, as some brokers/terminals glitch with "*" if symbols not in MarketWatch
        orders = mt5.history_orders_get(from_date, to_date) 
        
        if orders is None or len(orders) == 0:
            # Fallback: Try with group filter just in case default is empty
            orders = mt5.history_orders_get(from_date, to_date, group="*")

        if orders is None: 
            logger.warning(f"history_orders_get returned None. Last Error: {mt5.last_error()}")
            return []

        data = []
        for o in orders:
            # Map State
            state = "UNKNOWN"
            if o.state == mt5.ORDER_STATE_STARTED: state = "STARTED"
            elif o.state == mt5.ORDER_STATE_PLACED: state = "PLACED"
            elif o.state == mt5.ORDER_STATE_CANCELED: state = "CANCELED"
            elif o.state == mt5.ORDER_STATE_PARTIAL: state = "PARTIAL"
            elif o.state == mt5.ORDER_STATE_FILLED: state = "FILLED"
            elif o.state == mt5.ORDER_STATE_REJECTED: state = "REJECTED"
            elif o.state == mt5.ORDER_STATE_EXPIRED: state = "EXPIRED"
            elif o.state == mt5.ORDER_STATE_REQUEST_ADD: state = "REQ_ADD"
            elif o.state == mt5.ORDER_STATE_REQUEST_MODIFY: state = "REQ_MOD"
            elif o.state == mt5.ORDER_STATE_REQUEST_CANCEL: state = "REQ_DEL"
            
            # Map Type
            o_type = "BUY" if o.type == mt5.ORDER_TYPE_BUY else "SELL"
            if o.type == mt5.ORDER_TYPE_BUY_LIMIT: o_type = "BUY_LIMIT"
            elif o.type == mt5.ORDER_TYPE_SELL_LIMIT: o_type = "SELL_LIMIT"
            elif o.type == mt5.ORDER_TYPE_BUY_STOP: o_type = "BUY_STOP"
            elif o.type == mt5.ORDER_TYPE_SELL_STOP: o_type = "SELL_STOP"
            elif o.type == mt5.ORDER_TYPE_CLOSE_BY: o_type = "CLOSE_BY"

            data.append({
                "ticket": int(o.ticket),
                "symbol": str(o.symbol),
                "type": str(o_type),
                "state": str(state),
                "volume": float(o.volume_initial),
                "price": float(o.price_open),
                "time": int(o.time_setup),
                "comment": str(o.comment)
            })
        
        # Sort by time desc
        data.sort(key=lambda x: x['time'], reverse=True)
        return data

    def modify_position(self, ticket, sl, tp):
        if not self.connect(): return {"status": "error", "message": "MT5 Disconnected"}

        # Try to find in positions first
        is_pending = False
        res = mt5.positions_get(ticket=ticket)
        if not res:
            # Try orders
            res = mt5.orders_get(ticket=ticket)
            is_pending = True
        
        if not res:
            return {"status": "error", "message": "Position/Order not found"}
        
        item = res[0]
        symbol = item.symbol

        # Normalization
        info = mt5.symbol_info(symbol)
        digits = info.digits if info else 5
        
        if sl > 0: sl = round(float(sl), digits)
        if tp > 0: tp = round(float(tp), digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "sl": sl,
            "tp": tp
        }
        
        if is_pending:
             # For pending orders, we use TRADE_ACTION_MODIFY
             request["action"] = mt5.TRADE_ACTION_MODIFY
             request["order"] = ticket
             request["price"] = item.price_open # Must re-send details? 
             # Actually for modifying Pending Order specific fields (Price/SL/TP), we use TRADE_ACTION_MODIFY
             # Sl/TP modification on existing position uses TRADE_ACTION_SLTP
             # Correct logic for Pending Order Modify:
             request["sl"] = sl
             request["tp"] = tp
             # We must include original params 
             request["type"] = item.type
             request["type_time"] = item.type_time
             request["type_filling"] = item.type_filling
        else:
             request["position"] = ticket

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
             return {"status": "error", "message": f"{result.comment} ({result.retcode})"}
        
        return {"status": "success", "message": "Updated SL/TP"}

    def close_position(self, ticket):
        if not self.connect(): return {"status": "error", "message": "MT5 Disconnected"}
        
        # Check if Position (Active)
        positions = mt5.positions_get(ticket=ticket)
        if positions:
            pos = positions[0]
            # Close Logic
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(pos.symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(request)
            if res.retcode == 10030:
                request["type_filling"] = mt5.ORDER_FILLING_RETURN
                res = mt5.order_send(request)
            
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                 return {"status": "error", "message": f"{res.comment}"}
            return {"status": "success", "ticket": res.order}

        # Check if Order (Pending) -> Cancel/Remove
        orders = mt5.orders_get(ticket=ticket)
        if orders:
            o = orders[0]
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }
            res = mt5.order_send(request)
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                 return {"status": "error", "message": f"{res.comment}"}
            return {"status": "success", "message": "Order Cancelled"}
            
        return {"status": "error", "message": "Ticket not found"}

    def get_deals_history(self, from_date, to_date):
        if not self.connect(): return []
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        
        data = []
        for d in deals:
            data.append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "type": d.type, 
                "volume": d.volume,
                "profit": d.profit,
                "time": d.time
            })
        return data

mt5_connector = MT5Connector()
