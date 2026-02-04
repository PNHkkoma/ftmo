
import MetaTrader5 as mt5
print("Initializing auto...")
if not mt5.initialize():
    print("Init failed")
else:
    print(f"Connected to: {mt5.terminal_info().path}")
    print(f"Account: {mt5.account_info().login}")
    print(f"Pos: {len(mt5.positions_get() or [])}")
    print(f"Orders: {len(mt5.orders_get() or [])}")
    mt5.shutdown()
