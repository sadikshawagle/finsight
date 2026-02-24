from fastapi import APIRouter
from services.price_fetcher import fetch_market_overview, fetch_crypto_prices

router = APIRouter()


@router.get("/markets/overview")
def get_markets_overview():
    """Return current prices for all indices, commodities, and crypto."""
    indices_and_commodities = fetch_market_overview()
    crypto                  = fetch_crypto_prices()

    # Shape into sections for the frontend
    indices    = {}
    commodities = {}
    for name, data in indices_and_commodities.items():
        if name in ("Gold", "Silver", "Oil (WTI)"):
            commodities[name] = data
        else:
            indices[name] = data

    return {
        "indices":     indices,
        "commodities": commodities,
        "crypto":      crypto,
    }
