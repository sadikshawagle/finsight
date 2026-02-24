"""
Sends financial news articles to Groq (LLaMA 3.3 70B) for analysis.
Returns structured signal data: BUY / SELL / AVOID / WATCH with clear reasoning.
Compatible with Python 3.9+
"""
from __future__ import annotations
from typing import Optional, Dict
from groq import Groq
import json
import logging
from datetime import datetime
import pytz
from config import settings

log = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)
AEST   = pytz.timezone("Australia/Sydney")
MODEL  = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """\
You are FinSight's AI financial signal engine. You give retail investors crystal-clear,
honest trading signals based on financial news. You cover ASX, US equities, crypto, and commodities.

You MUST respond ONLY with valid JSON. No text outside the JSON.

━━━ SIGNAL LOGIC — CRITICAL ━━━

BUY — Price is at a GOOD ENTRY POINT because of a positive catalyst in this news.
      Example: "Stock dropped 15% on fears but earnings beat — oversold, buy the dip."
      Example: "New contract win not priced in yet — stock will re-rate upward."

SELL — Time to EXIT or TAKE PROFITS. Use when:
       • Stock already UP a lot and news shows the peak is in (lock in gains)
       • Stock is DOWN and news confirms MORE downside is coming (cut losses NOW)
       • Valuation is stretched with no catalyst to justify it
       Always state clearly: "sell because it has further to fall" OR "sell to lock in gains"

AVOID — Do NOT enter. Too risky right now. Wait for clarity.
        Use when: uncertainty is high, downside unquantifiable, better opportunities exist.

WATCH — Interesting but not actionable yet. State exactly what trigger would make it BUY/SELL.

━━━ REASONING RULES ━━━
Your reasoning MUST always answer these questions explicitly:
1. What exactly did the news say? (quote the key fact)
2. What does this mean for the stock price direction? (up or down, and why)
3. Is the stock likely already priced this in, or is the market slow to react?
4. What is the specific risk that could make this signal wrong?

Impact scale: -1.0 (catastrophic) to +1.0 (transformative positive)
Confidence: 0.0 to 1.0 — multiply your raw score by the source credibility given.
"""


def _aest_now() -> str:
    return datetime.now(AEST).strftime("%Y-%m-%d %H:%M AEST")


def analyze_article(article: Dict) -> Optional[Dict]:
    """
    Send one article to Groq and return a structured signal dict, or None if irrelevant.
    """
    pub_str = article["published_at"].strftime("%Y-%m-%d %H:%M UTC") \
              if isinstance(article["published_at"], datetime) \
              else str(article["published_at"])

    prompt = f"""Analyze this financial news and generate a trading signal with clear reasoning.

ARTICLE:
Title:       {article['title']}
Source:      {article['source']}  (credibility: {article['credibility']:.0%})
Published:   {pub_str}
Content:     {article['content'][:2500]}

Current time (AEST): {_aest_now()}

Return EXACTLY this JSON — no other text:
{{
  "tickers": [],
  "market": "US",
  "signal": "BUY",
  "confidence": 0.00,
  "impact": 0.00,
  "summary": "One plain-English sentence. Must say WHY — e.g. 'IBM down 34% on weak cloud revenue — further decline likely as clients switch to AWS.'",
  "reasoning": "4-5 sentences that MUST cover: (1) The exact news fact and what happened. (2) Why this pushes the price UP or DOWN. (3) Whether the market has already priced this in or not. (4) The main risk that could make this signal wrong. (5) The final verdict: exactly why BUY/SELL/AVOID/WATCH right now.",
  "signal_logic": "One sentence explaining the core logic. For SELL: state if it's 'cut losses — more downside' OR 'take profits — peak is in'. For BUY: state if it's 'buy the dip' OR 'buy the breakout'. For AVOID: state what you're waiting for.",
  "relevant": true,
  "skip_reason": ""
}}

Hard rules:
1. market must be: ASX | US | CRYPTO | COMMODITY
2. No market-moving content → relevant=false
3. ASX tickers need .AX suffix (BHP.AX, CBA.AX)
4. Crypto: symbol only (BTC, ETH, SOL)
5. Commodity: GOLD, SILVER, OIL
6. confidence = raw confidence × {article['credibility']:.2f}
7. Max 4 tickers
8. SELL can mean "stock is falling and will fall more" OR "stock is up and you should lock profits" — be explicit which one
9. BUY can mean "good entry after a dip" OR "momentum play going higher" — be explicit which one
"""

    try:
        response = client.chat.completions.create(
            model    = MODEL,
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature = 0.1,
            max_tokens  = 1200,
        )

        text = response.choices[0].message.content.strip()

        # Strip markdown fences if model wraps output
        if text.startswith("```"):
            parts = text.split("```")
            text  = parts[1] if len(parts) > 1 else text
            if text.lower().startswith("json"):
                text = text[4:]

        result = json.loads(text.strip())
        return result

    except json.JSONDecodeError as e:
        log.error(f"Groq returned invalid JSON for '{article['title']}': {e}")
        return None
    except Exception as e:
        log.error(f"Groq analysis failed for '{article['title']}': {e}")
        return None
