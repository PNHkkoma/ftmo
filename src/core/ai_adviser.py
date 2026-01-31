
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
        Analyze this setup for FTMO 100k Challenge (Risk optimized).
        Symbol: {symbol}
        Price: {market_data['close']:.2f}
        Bias: {market_data['bias']}
        EMA20: {market_data['ema20']:.2f}
        EMA50: {market_data['ema50']:.2f}
        RSI: {market_data['rsi']:.1f}
        ATR: {market_data['atr']:.4f}

        Provide a JSON response with:
        - "action": "BUY", "SELL", or "WAIT"
        - "confidence": "HIGH", "MID", "LOW"
        - "entry": suggested entry price (or null)
        - "sl": suggested stop loss
        - "tp": suggested take profit
        - "reason": short explanation (max 10 words)
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
