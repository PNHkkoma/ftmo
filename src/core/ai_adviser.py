
from openai import OpenAI
import os
import time

class AIAdviser:
    def __init__(self, api_key=None, model="gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        
        self.last_call_time = {}
        self.cache = {}
        
    def analyze(self, symbol, market_data):
        if not self.client:
            return {"advice": "AI DISABLED", "reason": "No API Key"}

        # Cooldown check (avoid spamming AI for same symbol in short time)
        now = time.time()
        if symbol in self.last_call_time and (now - self.last_call_time[symbol] < 120):
             return self.cache.get(symbol, {"advice": "WAIT", "reason": "Cooldown"})

        prompt = f"""
        You are a senior proprietary trading advisor specialized in FTMO challenges.
        Your primary goal is CAPITAL PRESERVATION and RULE COMPLIANCE, not frequent trading.

        Account context:
        - FTMO Challenge
        - Account size: 100,000 USD
        - Strict daily and max drawdown rules
        - Prefer WAIT over low-quality trades

        Market snapshot:
        Symbol: {symbol}
        Current price: {market_data['close']:.2f}

        Technical context (lower timeframe):
        - Bias: {market_data['bias']}
        - EMA20: {market_data['ema20']:.2f}
        - EMA50: {market_data['ema50']:.2f}
        - RSI: {market_data['rsi']:.1f}
        - ATR: {market_data['atr']:.4f}

        Market regime analysis:
        - Identify if market is: TRENDING, PULLBACK, RANGE, or HIGH VOLATILITY
        - Assess whether recent move suggests:
        * healthy pullback
        * potential reversal
        * or dead-cat bounce after liquidation

        Risk & psychology filters:
        - Avoid trades after strong impulsive moves
        - Avoid counter-trend trades without confirmation
        - Avoid tight stop loss in high ATR conditions
        - Prefer confirmation over prediction

        Decision rules:
        - If conditions are unclear or risky, choose WAIT
        - BUY or SELL only if risk-to-reward is clearly favorable (>= 1:2)
        - Suggested SL must respect current volatility (ATR-based)

        Respond ONLY in valid JSON with:
        {
        "action": "BUY" | "SELL" | "WAIT",
        "confidence": "HIGH" | "MID" | "LOW",
        "market_phase": "TREND" | "PULLBACK" | "RANGE" | "VOLATILE",
        "entry": number or null,
        "sl": number or null,
        "tp": number or null,
        "risk_note": "max 8 words",
        "reason": "max 12 words"
        }

        Be conservative. FTMO survival > profit.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional forex trader. Be conservative and precise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            # Save to cache
            import json
            result_json = json.loads(result_text)
            self.cache[symbol] = result_json
            self.last_call_time[symbol] = now
            
            return result_json
            
        except Exception as e:
            return {"advice": "ERROR", "reason": str(e)}
