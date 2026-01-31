import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime
import os

# =========================
# CONFIG GIAO DỊCH
# =========================
SYMBOLS = {
    "XAUUSD": mt5.TIMEFRAME_M5,
    "BTCUSD": mt5.TIMEFRAME_M5,
    "EURUSD": mt5.TIMEFRAME_M5
}

ACCOUNT_SIZE = 100_000
MAX_DAILY_LOSS = 5_000
MAX_TOTAL_LOSS = 10_000
SAFE_DAILY_BUFFER = 4_500

RISK_PER_TRADE = 0.005  # 0.5%

# =========================
# CONFIG AI – AN TOÀN CHI PHÍ
# =========================
AI_ENABLED = True

AI_MIN_INTERVAL = 120          # 🔒 tăng lên 2 phút
MAX_AI_CALLS_PER_DAY = 30      # 🔒 giảm mạnh để test
AI_MAX_FAILS = 3               # 🔒 quá 3 lỗi thì tắt AI

# =========================
# BIẾN KIỂM SOÁT AI
# =========================
LAST_AI_CALL = {}
AI_CALL_COUNT = 0
AI_FAIL_COUNT = 0
AI_DAY_START = time.time()

# =========================
# INIT MT5
# =========================
if not mt5.initialize():
    raise RuntimeError("❌ Không kết nối được MT5")

account = mt5.account_info()
print(f"✅ KẾT NỐI MT5 THÀNH CÔNG | Balance: {account.balance} | Equity: {account.equity}")

# =========================
# UTILS
# =========================
def get_rates(symbol, timeframe, n=100):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def atr(df, period=14):
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

# =========================
# FTMO RISK GUARD
# =========================
def ftmo_guard():
    acc = mt5.account_info()
    daily_dd = acc.balance - acc.equity

    if daily_dd <= -SAFE_DAILY_BUFFER:
        return False, "⚠️ GẦN CHẠM DAILY LOSS – DỪNG AI & GIAO DỊCH"

    if acc.equity <= ACCOUNT_SIZE - MAX_TOTAL_LOSS:
        return False, "❌ CHẠM MAX LOSS – FAIL FTMO"

    return True, "OK"

# =========================
# STRATEGY
# =========================
def market_bias(df):
    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
    price = df['close'].iloc[-1]

    if price > ema20 > ema50:
        return "BULLISH"
    elif price < ema20 < ema50:
        return "BEARISH"
    return "RANGE"

def trade_plan(symbol, df):
    bias = market_bias(df)
    price = df['close'].iloc[-1]
    current_atr = atr(df)

    if bias == "BULLISH":
        return {
            "symbol": symbol,
            "direction": "BUY",
            "entry": round(price, 2),
            "sl": round(price - 1.5 * current_atr, 2),
            "tp": round(price + 3 * current_atr, 2),
            "bias": bias,
            "atr": round(current_atr, 2)
        }

    if bias == "BEARISH":
        return {
            "symbol": symbol,
            "direction": "SELL",
            "entry": round(price, 2),
            "sl": round(price + 1.5 * current_atr, 2),
            "tp": round(price - 3 * current_atr, 2),
            "bias": bias,
            "atr": round(current_atr, 2)
        }

    return None

# =========================
# AI ADVISOR – GEMINI (CÓ CHẶN BUDGET)
# =========================
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("❌ CHƯA SET OPENAI_API_KEY – TẮT AI")
    AI_ENABLED = False
else:
    client = OpenAI(api_key=OPENAI_API_KEY)


print("test")

def test_openai_connection():
    print("🔍 KIỂM TRA KẾT NỐI OPENAI (SAFE)...")

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input="OK",
            max_output_tokens=16,
            temperature=0
        )
        print("✅ OPENAI OK")
        return True

    except Exception as e:
        print("❌ LỖI OPENAI:", e)
        return False


if AI_ENABLED:
    if not test_openai_connection():
        print("⛔ TẮT AI – KHÔNG KẾT NỐI ĐƯỢC OPENAI")
        AI_ENABLED = False
    else:
        print("✅ OPENAI SẴN SÀNG HOẠT ĐỘNG")



def ai_advisor(plan):
    global AI_CALL_COUNT, AI_DAY_START, AI_FAIL_COUNT

    if not AI_ENABLED:
        return "AI OFF"
    else:
        print("chạy ai_advisor")

    # FTMO guard trước
    ok, msg = ftmo_guard()
    if not ok:
        return msg

    now = time.time()

    # reset counter mỗi ngày
    if now - AI_DAY_START >= 86400:
        AI_CALL_COUNT = 0
        AI_DAY_START = now
        print("🔄 RESET AI COUNTER")

    if AI_CALL_COUNT >= MAX_AI_CALLS_PER_DAY:
        return "⛔ AI ĐÃ BỊ CHẶN (HẾT QUOTA NGÀY)"

    last = LAST_AI_CALL.get(plan["symbol"], 0)
    if now - last < AI_MIN_INTERVAL:
        return "⏳ AI COOLDOWN"

    prompt = f"""
FTMO 100k – Đánh giá nhanh kèo:

Symbol: {plan['symbol']}
Direction: {plan['direction']}
Entry: {plan['entry']}
SL: {plan['sl']}
TP: {plan['tp']}
ATR: {plan['atr']}
Bias: {plan['bias']}

Chỉ trả lời:
- SAFE hoặc CAUTION
- Xác suất: LOW / MID / HIGH
"""

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.2,
            max_output_tokens=80
        )

        AI_CALL_COUNT += 1
        LAST_AI_CALL[plan["symbol"]] = now

        return resp.output_text.strip()

    except Exception as e:
        AI_FAIL_COUNT += 1
        print("❌ AI ERROR:", e)

        if AI_FAIL_COUNT >= AI_MAX_FAILS:
            print("⛔ AI FAIL QUÁ NHIỀU – TẮT AI")
            disable_ai()

        return "AI ERROR"

def disable_ai():
    global AI_ENABLED
    AI_ENABLED = False





print("🚀 START TRADING LOOP")

while True:
    for symbol, tf in SYMBOLS.items():
        print(f"\n📊 CHECK {symbol}")

        df = get_rates(symbol, tf)
        if df is None or len(df) < 50:
            print("⚠️ Không đủ dữ liệu")
            continue

        plan = trade_plan(symbol, df)

        if plan is None:
            print("➖ Không có kèo")
            continue

        print("📌 PLAN:", plan)

        advice = ai_advisor(plan)
        print("🤖 AI:", advice)

    time.sleep(60)  # 🔒 mỗi phút 1 vòng
