from fastapi import APIRouter, HTTPException
from services.price_fetcher import fetch_single_price

router = APIRouter()


@router.get("/prices/{ticker}")
def get_price(ticker: str):
    """Fetch current price for any single ticker (stock, index, commodity)."""
    data = fetch_single_price(ticker.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    return data
