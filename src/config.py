
import os
from dotenv import load_dotenv

load_dotenv()

# Trading Symbols & Timeframes
# Default symbols, user can add more via UI
DEFAULT_SYMBOLS = [
    "XAUUSD",
    "BTCUSD",
    "EURUSD"
]

TIMEFRAME = 5 # M5, using integer for MT5 (will be converted in connector)

# FTMO Account Settings
ACCOUNT_SIZE = 100_000
MAX_DAILY_LOSS = 5_000
MAX_TOTAL_LOSS = 10_000
SAFE_DAILY_BUFFER = 4_500  # Stop trading if loss hits this

# Risk Management
RISK_PER_TRADE = 0.005  # 0.5%
RISK_REWARD_RATIO = 2.0

# AI Configuration
AI_ENABLED = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MODEL = "gpt-4o-mini"
AI_MAX_TOKENS = 150

# App Settings
REFRESH_RATE = 2  # Seconds to poll prices
