
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

    # ATR MA for status
    df['atr_ma'] = df['atr'].rolling(20).mean()

    return df

def analyze_market_structure(df, timeframe_label="M5"):
    """
    Returns bias and key metrics with dynamic lookback based on timeframe
    """
    if df is None: return {}
    
    last = df.iloc[-1]
    
    bias = "RANGE"
    if last['close'] > last['ema20'] > last['ema50']:
        bias = "BULLISH"
    elif last['close'] < last['ema20'] < last['ema50']:
        bias = "BEARISH"

    # ATR Status
    atr_status = "Normal"
    if pd.notna(last['atr']) and pd.notna(last['atr_ma']):
        if last['atr'] > last['atr_ma'] * 1.5:
            atr_status = "Expanding"
        elif last['atr'] < last['atr_ma'] * 0.7:
            atr_status = "Low"
        else:
            atr_status = "Normal"

    # Lookback Logic
    lookback = 40 # Default fallback
    
    # User Rules: 
    # M5 -> 150
    # M15 -> 100
    # H1 -> 75
    # H4 -> 40
    # D1 -> 15
    
    tf = str(timeframe_label).upper()
    if "M1" in tf: lookback = 150 # Treat M1 same as M5 for safety
    elif "M5" in tf: lookback = 150
    elif "M15" in tf: lookback = 100
    elif "H1" in tf: lookback = 75
    elif "H4" in tf: lookback = 40
    elif "D1" in tf: lookback = 15

    # Simple SMC Detection (Liquidity / FVG)
    smc = detect_smart_money_concepts(df, lookback)

    return {
        "bias": bias,
        "close": last['close'],
        "ema20": last['ema20'],
        "ema50": last['ema50'],
        "atr": last['atr'],
        "rsi": last['rsi'],
        "atr_status": atr_status,
        "liquidity_state": smc['liquidity_state'],
        "fvg_state": smc['fvg_state']
    }

def detect_smart_money_concepts(df, lookback=20):
    try:
        # Safety check
        if len(df) < lookback + 5: 
            lookback = len(df) - 5
        
        if lookback < 5: 
            return {"liquidity_state": "Unknown", "fvg_state": "Unknown"}
        
        last = df.iloc[-1]
        
        # FVG Detection: Scan backwards 'lookback' candles
        fvg_state = "Absent"
        
        start_idx = len(df) - 1
        end_idx = max(2, len(df) - lookback)

        for i in range(start_idx, end_idx, -1):
            c_prev2 = df.iloc[i-2] # Candle 1
            c_curr = df.iloc[i]    # Candle 3
            
            # Bullish FVG
            if c_prev2['high'] < c_curr['low']: 
                fvg_state = "Present (Bullish)"
                break
                
            # Bearish FVG
            elif c_prev2['low'] > c_curr['high']:
                fvg_state = "Present (Bearish)"
                break
        
        # Liquidity Sweep
        recent_high = df['high'].iloc[-lookback:-1].max()
        recent_low = df['low'].iloc[-lookback:-1].min()
        
        liquidity_state = "Resting"
        
        if last['high'] > recent_high and last['close'] < recent_high:
            liquidity_state = "Sweep High (Bearish)"
        elif last['low'] < recent_low and last['close'] > recent_low:
            liquidity_state = "Sweep Low (Bullish)"
            
        return {"liquidity_state": liquidity_state, "fvg_state": fvg_state}
            
    except Exception as e:
        print(f"SMC Error: {e}")
        return {"liquidity_state": "Unknown", "fvg_state": "Unknown"}
