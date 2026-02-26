from pydantic_settings import BaseSettings
from urllib.parse import urlparse


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = "FinSight <onboarding@resend.dev>"

    FREE_SIGNAL_LIMIT: int = 3
    FREE_WATCHLIST_LIMIT: int = 5

    class Config:
        env_file = ".env"


settings = Settings()

# ── Source credibility map (keyed by domain) ──────────────────────────────────
SOURCE_CREDIBILITY: dict[str, float] = {
    # Tier 1 — Institutional
    "reuters.com":           0.98,
    "bloomberg.com":         0.97,
    "wsj.com":               0.96,
    "ft.com":                0.95,
    "afr.com":               0.93,
    # Tier 2 — Credible financial media
    "barrons.com":           0.92,
    "economist.com":         0.91,
    "cnbc.com":              0.88,
    "marketwatch.com":       0.87,
    "theaustralian.com.au":  0.85,
    "abc.net.au":            0.84,
    "morningstar.com":       0.82,
    "skynews.com.au":        0.82,
    "seekingalpha.com":      0.80,
    # Tier 3 — Crypto / commodity specific
    "coindesk.com":          0.79,
    "cointelegraph.com":     0.76,
    "kitco.com":             0.75,
    "businessinsider.com":   0.75,
    "fool.com.au":           0.68,
    "fool.com":              0.68,
    # Social
    "twitter.com":           0.70,
    "x.com":                 0.70,
}

# Minimum credibility to even attempt Claude analysis
MIN_CREDIBILITY = 0.68


def get_credibility(url: str) -> float:
    """Return the credibility score for a URL's domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return 0.60

    if domain in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[domain]

    # Suffix match (e.g. sub.reuters.com)
    for key, score in SOURCE_CREDIBILITY.items():
        if domain.endswith(key):
            return score

    return 0.60  # Unknown source
