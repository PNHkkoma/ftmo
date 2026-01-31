
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
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
            if not mt5.initialize():
                logger.error("Initialize failed, error code =", mt5.last_error())
                return False
            self.connected = True
            logger.info(f"MT5 Connected. Terminal Info: {mt5.terminal_info()}")
        return True

    def get_account_info(self):
        if not self.connect(): return None
        return mt5.account_info()

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
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL] else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Adjust for pending orders
        if order_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP]:
             request["action"] = mt5.TRADE_ACTION_PENDING

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.retcode} - {result.comment}")
            return {"status": "error", "message": result.comment}
        
        logger.info(f"Order placed: {result}")
        return {"status": "success", "ticket": result.order}

mt5_connector = MT5Connector()
