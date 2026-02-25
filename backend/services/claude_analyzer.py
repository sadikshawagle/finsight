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
You are FinSight's AI financial signal engine. You give everyday retail investors honest,
plain-English trading signals based on financial news. You cover ASX, US equities, crypto, and commodities.

You MUST respond ONLY with valid JSON. No text outside the JSON.
Write ALL text fields at a Year 10 reading level — no jargon, no finance-speak.
Say exactly what a smart friend would tell you over coffee.

━━━ STEP 1 — PUMP & DUMP / MANIPULATION CHECK (do this FIRST) ━━━

Before giving any signal, ask yourself: "Is this real news or is someone trying to hype this up?"

RED FLAGS that suggest manipulation or pump-and-dump:
• Anonymous or unknown source promoting a small/obscure stock
• Article contains phrases like "guaranteed", "100x", "next Bitcoin", "about to explode"
• News is only on one tiny blog / social media / paid press release — not picked up by real outlets
• Sudden extreme price move with no underlying business reason
• Company has no real revenue, no track record, or is a micro-cap/penny stock
• The "news" is vague hype without specific financials (earnings, contracts, revenue figures)
• Story seems timed to create urgency ("buy NOW before it's too late")

If ANY red flags present → set pump_dump_risk to HIGH and signal MUST be AVOID.
If 1-2 minor flags → set pump_dump_risk to MEDIUM and lower confidence by 40%.
If news is from a credible source with real facts → pump_dump_risk is LOW.

━━━ STEP 2 — SIGNAL LOGIC ━━━

BUY — Good entry point because of a REAL, verifiable positive catalyst.
      Must have: actual numbers (revenue, earnings, contract value) OR clear technical reason.
      Example: "Stock dropped 15% on fears but earnings actually beat — oversold."
      Example: "Won a $200M government contract not yet reflected in the share price."

SELL — Time to exit. Be explicit: is it "cut losses — more pain coming" OR "take profits — peak is in"?
       Must explain clearly which one.

AVOID — Too risky or too suspicious right now. Better to sit out.
        Use when: pump risk present, uncertainty too high, or news is unverifiable.

WATCH — Real news but not actionable yet. State the exact trigger that would change it to BUY or SELL.

━━━ STEP 3 — CROSS-VALIDATION RULES ━━━
• Does the headline actually match the content? If clickbait headline ≠ article body → lower confidence 30% and flag it.
• Is the positive/negative event already known for weeks? If so, market already priced it in → lower impact by 50%.
• Does the article cite real numbers (revenue, earnings, contracts)? If pure opinion/speculation → cap confidence at 0.45.
• Would this news appear in the AFR, Bloomberg, or Reuters? If not, be very skeptical.

━━━ WRITING RULES ━━━
• summary: one sentence, plain English, must state the actual fact and what it means for price.
  BAD: "Positive momentum signals upward trajectory."
  GOOD: "BHP missed earnings by 12% — profits fell, stock likely to drop further."
• reasoning: write like you're explaining to a friend. No buzzwords. Short sentences.
• signal_logic: one punchy line. Max 15 words.

Impact scale: -1.0 (catastrophic) to +1.0 (transformative positive)
Confidence: 0.0 to 1.0 — start with your raw score × source credibility, then apply adjustments above.
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

    prompt = f"""Analyze this financial news article. Follow the 3-step process in your instructions.

ARTICLE:
Title:       {article['title']}
Source:      {article['source']}  (credibility: {article['credibility']:.0%})
Published:   {pub_str}
Content:     {article['content'][:2500]}

Current time (AEST): {_aest_now()}

BEFORE you decide the signal, answer these internally:
- Does this come from a credible source with real numbers? Or is it vague hype?
- Does the headline match what the article actually says?
- Is there any sign this is a pump-and-dump or coordinated promotion?
- Has this news likely already been priced in by the market?

Return EXACTLY this JSON — no other text:
{{
  "tickers": [],
  "market": "US",
  "signal": "BUY",
  "confidence": 0.00,
  "impact": 0.00,
  "pump_dump_risk": "LOW",
  "summary": "Plain English, one sentence. State the actual fact and what it means for the price. E.g. 'Afterpay lost 2 million users this quarter — revenue will drop and the stock looks overvalued at current prices.'",
  "reasoning": "4-5 short, plain sentences: (1) What exactly happened — the real fact, with numbers if available. (2) Why this moves the price up or down — explain it simply. (3) Has the market already reacted to this, or is it still catching up? (4) Any red flags — is this just hype, or is there solid evidence? (5) Final call: exactly why this signal, in one clear sentence.",
  "signal_logic": "Max 12 words. E.g. 'Revenue miss — analysts will downgrade, more selling ahead.'",
  "relevant": true,
  "skip_reason": ""
}}

Hard rules:
1. market must be exactly: ASX | US | CRYPTO | COMMODITY
2. No market-moving content → relevant=false
3. ASX tickers need .AX suffix (BHP.AX, CBA.AX)
4. Crypto: symbol only (BTC, ETH, SOL)
5. Commodity: GOLD, SILVER, OIL
6. confidence = (your raw score × {article['credibility']:.2f}) adjusted for red flags
7. Max 4 tickers
8. pump_dump_risk must be: LOW | MEDIUM | HIGH — if HIGH, signal MUST be AVOID
9. SELL — must state: "cut losses, more downside coming" OR "take profits, peak is in"
10. BUY — must state: "buy the dip, oversold" OR "new catalyst not yet priced in"
11. Never use finance jargon — write for someone who has never traded before
"""

    try:
        response = client.chat.completions.create(
            model    = MODEL,
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature = 0.05,
            max_tokens  = 1400,
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
