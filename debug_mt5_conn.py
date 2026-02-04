
import MetaTrader5 as mt5
import sys

print("Script starting...", flush=True)

if not mt5.initialize():
    print("Initialize failed")
    mt5.shutdown()
    sys.exit()

print("-" * 30)
print("DEBUG CONNECTION INFO")
print("-" * 30)

term = mt5.terminal_info()
if term:
    print(f"PATH:    {term.path}")
    print(f"NAME:    {term.name}")
    print(f"CONNECTED: {term.connected}")
else:
    print("TERMINAL INFO: None")

acc = mt5.account_info()
if acc:
    print(f"ACCOUNT: {acc.login}")
    print(f"SERVER:  {acc.server}")
    print(f"BALANCE: {acc.balance}")
    print(f"EQUITY:  {acc.equity}")
else:
    print("ACCOUNT INFO: None (Not logged in?)")

print("-" * 30)
print("POSITIONS:", mt5.positions_total())
print("ORDERS:   ", mt5.orders_total())
mt5.shutdown()
