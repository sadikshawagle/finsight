"""
Payments router — Stripe placeholder.
Full Stripe integration will be added once Terms of Service + Privacy Policy pages are live.
"""
from fastapi import APIRouter

router = APIRouter()

PRO_PRICE_AUD   = 8.99
ELITE_PRICE_AUD = 15.99


@router.post("/payments/create-checkout")
def create_checkout():
    """Stripe checkout placeholder — full integration coming soon."""
    return {
        "status":  "coming_soon",
        "message": "Stripe payments are being set up. We'll email you when subscriptions are live.",
        "pricing": {
            "PRO":   f"${PRO_PRICE_AUD} AUD/month",
            "ELITE": f"${ELITE_PRICE_AUD} AUD/month",
        },
    }
