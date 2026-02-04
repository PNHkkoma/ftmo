import MetaTrader5 as mt5
from datetime import datetime, timedelta

mt5.initialize()
print(f"Account: {mt5.account_info().login}")

# Test history_deals_get (this is what /api/history uses)
from_date = datetime.now() - timedelta(days=30)
to_date = datetime.now()

print("\n=== HISTORY DEALS ===")
deals = mt5.history_deals_get(from_date, to_date)
if deals:
    print(f"Found {len(deals)} deals")
    for d in deals[:5]:
        print(f"  {datetime.fromtimestamp(d.time)} | {d.symbol} | Profit: {d.profit}")
else:
    print(f"No deals. Error: {mt5.last_error()}")

print("\n=== HISTORY ORDERS ===")
orders = mt5.history_orders_get(from_date, to_date)
if orders:
    print(f"Found {len(orders)} orders")
    for o in orders[:5]:
        print(f"  {datetime.fromtimestamp(o.time_setup)} | {o.symbol} | State: {o.state}")
else:
    print(f"No orders. Error: {mt5.last_error()}")

mt5.shutdown()
