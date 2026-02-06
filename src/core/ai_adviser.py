
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
        if symbol in self.last_call_time and (now - self.last_call_time[symbol] < 20):
             return self.cache.get(symbol, {"advice": "WAIT", "reason": "Cooldown"})
        # print(market_data)
        # --- Context Extraction ---
        current_session = market_data.get('session', 'Unknown')
        dxy_bias = market_data.get('dxy_bias', 'Neutral')
        liquidity_state = market_data.get('liquidity_state', 'Unknown')
        fvg_state = market_data.get('fvg_state', 'Unknown')
        
        market_data.setdefault('htf_bias', 'Neutral')
        market_data.setdefault('ltf_bias', market_data.get('bias', 'Neutral'))
        market_data.setdefault('atr_status', 'Normal')

        prompt = f"""
        You are a Senior Institutional Quant Trader & FTMO Risk Manager.
        Your sole mandate is to PASS the FTMO 100K Challenge through capital preservation,
        strict rule compliance, and high-quality institutional setups.

        Core principle:
        Survival > Profit.
        WAIT is preferable to low-quality trades, but VALID B-setups are allowed when risk is controlled.

        ACCOUNT CONTEXT:
        - Model: FTMO 100K Challenge
        - Max daily loss: 5% | Max total drawdown: 10%
        - Risk per trade: FIXED 0.5% (do NOT calculate lot size)
        - No revenge trading, no overtrading

        MARKET DATA INPUT:
        - Symbol: {symbol} | Current Price: {market_data['close']}
        - Session: {current_session} | News Event: {market_data.get('news_event', 'No Data')}
        - DXY Bias: {dxy_bias}

        TECHNICAL CONTEXT:
        - HTF Bias (H1/H4): {market_data['htf_bias']}
        - LTF Structure (M5/M15): {market_data['ltf_bias']}
        - EMA20: {market_data['ema20']} | EMA50: {market_data['ema50']}
        - RSI: {market_data['rsi']} | ATR: {market_data['atr']} ({market_data['atr_status']})

        LIQUIDITY & STRUCTURE CONTEXT:
        - Liquidity State: {liquidity_state} | FVG State: {fvg_state}

        MANDATORY FILTERS (HARD RULES):
        1. TREND setups require HTF and LTF bias alignment.
        2. If HTF is Neutral/Range: 
        - You MAY trade Liquidity Sweep or Mean Reversion setups on LTF.
        - These setups are MAXIMUM quality "B".
        3. If liquidity_state or fvg_state is 'Unknown' → WAIT (Absent / Resting is acceptable).
        4. News filter: High Impact News → WAIT (HARD). No Data → proceed with caution.
        5. Minimum Risk:Reward must be >= 1:2.
        6. Stop Loss must be >= 1.5 × ATR.

        EXECUTION LOGIC:
        - BUY or SELL only if: Market Structure Shift (BOS/MSB) confirmed + Entry at premium/discount.
        - Counter-trend allowed ONLY if: HTF is Neutral + Liquidity Sweep confirmed + RSI exhaustion/divergence.
        - If Action is BUY or SELL: 'entry', 'sl', and 'tp' MUST be numeric values.

        WAIT CLASSIFICATION:
        - WAIT_SOFT: No valid setup yet.
        - WAIT_RISK: FTMO risk constraints (news, volatility, drawdown protection).
        - WAIT_DATA: Missing or unreliable market data.

        OUTPUT FORMAT (STRICT JSON ONLY):
        {{
        "action": "BUY" | "SELL" | "WAIT",
        "setup_quality": "A" | "B" | "C" | "None",
        "market_regime": "TRENDING" | "REVERSAL" | "COMPRESSION" | "EXPANSION",
        "setup_type": "Trend Continuation" | "Mean Reversion" | "Liquidity Sweep" | "None",
        "execution": {{
            "entry": number | null,
            "sl": number | null,
            "tp": number | null,
            "risk_percent": 0.5
        }},
        "wait_type": "WAIT_SOFT" | "WAIT_RISK" | "WAIT_DATA" | "None",
        "wait_reasons": ["Clear", "specific", "reasons"],
        "risk_warning": "max 10 words",
        "professional_rationale": "max 25 words"
        }}

        Be professional and conservative. Explain WAIT reasons clearly.
        """

        # System message đóng vai trò "Kỷ luật thép"
        system_instruction = (
            "You are a Senior Institutional Quant & FTMO Risk Manager. "
            "You have zero tolerance for rule violations. Your goal is to pass the FTMO challenge "
            "by filtering for ONLY high-probability institutional setups. "
            "You must output STRICT JSON and nothing else."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.15,
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
            return {"action": "WAIT", "wait_type": "WAIT_DATA", "wait_reasons": [f"API Error: {str(e)}"]}
