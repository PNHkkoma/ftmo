import MetaTrader5 as mt5
from datetime import datetime, timedelta

# Connect
if not mt5.initialize():
    print("Failed to initialize")
    exit()

print(f"Connected to: {mt5.account_info().login}")
print(f"Data Path: {mt5.terminal_info().data_path}")

# Check current positions
print(f"\n=== CURRENT POSITIONS ===")
print(f"Total: {mt5.positions_total()}")
pos = mt5.positions_get()
if pos:
    for p in pos:
        print(f"  Ticket: {p.ticket}, Symbol: {p.symbol}, Profit: {p.profit}")
else:
    print("  None")

# Check pending orders
print(f"\n=== PENDING ORDERS ===")
print(f"Total: {mt5.orders_total()}")
orders = mt5.orders_get()
if orders:
    for o in orders:
        print(f"  Ticket: {o.ticket}, Symbol: {o.symbol}, Type: {o.type}")
else:
    print("  None")

# Check history orders (last 30 days)
print(f"\n=== HISTORY ORDERS (Last 30 Days) ===")
from_date = datetime.now() - timedelta(days=30)
to_date = datetime.now() + timedelta(days=1)

hist_orders = mt5.history_orders_get(from_date, to_date)
if hist_orders:
    print(f"Total: {len(hist_orders)}")
    for h in hist_orders[-10:]:  # Last 10
        print(f"  Time: {datetime.fromtimestamp(h.time_setup)}, Ticket: {h.ticket}, Symbol: {h.symbol}, State: {h.state}")
else:
    print(f"  None. Error: {mt5.last_error()}")

# Check history deals (last 30 days)
print(f"\n=== HISTORY DEALS (Last 30 Days) ===")
hist_deals = mt5.history_deals_get(from_date, to_date)
if hist_deals:
    print(f"Total: {len(hist_deals)}")
    for d in hist_deals[-10:]:  # Last 10
        print(f"  Time: {datetime.fromtimestamp(d.time)}, Ticket: {d.ticket}, Symbol: {d.symbol}, Profit: {d.profit}")
else:
    print(f"  None. Error: {mt5.last_error()}")

mt5.shutdown()
print("\n=== DONE ===")
