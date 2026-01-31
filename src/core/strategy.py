
import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    Calculates EMA20, EMA50, ATR(14), RSI(14)
    """
    if df is None or len(df) < 55:
        return None

    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # ATR
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr'] = df['tr'].rolling(14).mean()

    # RSI
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=False).mean()
    ma_down = down.ewm(com=13, adjust=False).mean()
    rs = ma_up / ma_down
    df['rsi'] = 100 - (100 / (1 + rs))

    return df

def analyze_market_structure(df):
    """
    Returns bias and key metrics
    """
    if df is None: return None
    
    last = df.iloc[-1]
    
    bias = "RANGE"
    if last['close'] > last['ema20'] > last['ema50']:
        bias = "BULLISH"
    elif last['close'] < last['ema20'] < last['ema50']:
        bias = "BEARISH"

    return {
        "bias": bias,
        "close": last['close'],
        "ema20": last['ema20'],
        "ema50": last['ema50'],
        "atr": last['atr'],
        "rsi": last['rsi']
    }
