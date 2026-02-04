
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import sys

PATH = r"D:\game\terminal64.exe"

print(f"--- DIAGNOSTIC START ---")
print(f"Target Path: {PATH}")

if not mt5.initialize(path=PATH):
    print(f"FAILED to initialize MT5 at {PATH}")
    print(f"Error: {mt5.last_error()}")
    sys.exit(1)

print(f"MT5 Initialized Successfully.")

# Terminal Info
term = mt5.terminal_info()
print(f"\n[TERMINAL]")
print(f"Path: {term.path}")
print(f"DataPath: {term.data_path}")
print(f"Connected: {term.connected}")
print(f"TradeAllowed: {term.trade_allowed}")

# Account Info
acc = mt5.account_info()
if acc:
    print(f"\n[ACCOUNT]")
    print(f"Login: {acc.login}")
    print(f"Name: {acc.name}")
    print(f"Server: {acc.server}")
    print(f"Balance: {acc.balance}")
    print(f"Equity: {acc.equity}")
else:
    print(f"\n[ACCOUNT] NONE - Not logged in?")

# Positions
print(f"\n[POSITIONS]")
pos = mt5.positions_get()
if pos:
    print(f"Count: {len(pos)}")
    for p in pos:
        print(f" - Ticket: {p.ticket} | Sym: {p.symbol} | Vol: {p.volume} | Profit: {p.profit}")
else:
    print("Count: 0 (No active positions)")
    print(f"LastError: {mt5.last_error()}")

# Orders
print(f"\n[PENDING ORDERS]")
orders = mt5.orders_get()
if orders:
    print(f"Count: {len(orders)}")
    for o in orders:
        print(f" - Ticket: {o.ticket} | Sym: {o.symbol} | Type: {o.type}")
else:
    print("Count: 0")

# History (Orders)
print(f"\n[HISTORY ORDERS (Last 30 Days)]")
from_date = datetime.now() - timedelta(days=30)
to_date = datetime.now() + timedelta(days=1)
hist_orders = mt5.history_orders_get(from_date, to_date)
if hist_orders:
    print(f"Count: {len(hist_orders)}")
    for h in hist_orders[-5:]: # Last 5
        print(f" - Time: {datetime.fromtimestamp(h.time_setup)} | Ticket: {h.ticket} | State: {h.state} | Sym: {h.symbol}")
else:
    print("Count: 0")
    print(f"LastError: {mt5.last_error()}")

# History (Deals)
print(f"\n[HISTORY DEALS (Last 30 Days)]")
hist_deals = mt5.history_deals_get(from_date, to_date)
if hist_deals:
    print(f"Count: {len(hist_deals)}")
    for d in hist_deals[-5:]:
        print(f" - Time: {datetime.fromtimestamp(d.time)} | Ticket: {d.ticket} | Profit: {d.profit}")
else:
    print("Count: 0")

mt5.shutdown()
print(f"\n--- DIAGNOSTIC END ---")
