"""
Portfolio router — holdings CRUD with live P&L, plus statistical analysis and optimization.
All endpoints require a valid JWT (Bearer token).
"""
from __future__ import annotations
from typing import Optional, List
import logging

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy import stats as scipy_stats
from scipy.optimize import minimize

import yfinance as yf

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, PortfolioHolding, BetaUser
from routers.auth import _get_current_user
from services.price_fetcher import fetch_single_price

router = APIRouter()
log    = logging.getLogger(__name__)

FREE_HOLDING_LIMIT = 3


# ── Pydantic models ────────────────────────────────────────────────────────────

class AddHoldingRequest(BaseModel):
    ticker:        str
    quantity:      float
    avg_buy_price: float
    currency:      Optional[str] = "USD"


class OptimizeRequest(BaseModel):
    tickers: List[str]
    amount:  float
    years:   Optional[int] = 5


# ── Internal helpers ───────────────────────────────────────────────────────────

def _holding_with_price(h: PortfolioHolding) -> dict:
    price_data    = fetch_single_price(h.ticker) or {}
    current_price = price_data.get("price")
    change_pct    = price_data.get("change_pct")

    cost_basis    = round(h.quantity * h.avg_buy_price, 4)
    current_value = round(h.quantity * current_price, 4) if current_price else None
    pnl           = round(current_value - cost_basis, 4) if current_value is not None else None
    pnl_pct       = round((pnl / cost_basis) * 100, 2) if pnl is not None and cost_basis else None

    return {
        "id":            h.id,
        "ticker":        h.ticker,
        "quantity":      h.quantity,
        "avg_buy_price": h.avg_buy_price,
        "currency":      h.currency,
        "added_at":      h.added_at.isoformat() if h.added_at else None,
        "current_price": current_price,
        "change_pct":    change_pct,
        "current_value": current_value,
        "cost_basis":    cost_basis,
        "pnl":           pnl,
        "pnl_pct":       pnl_pct,
    }


def _compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta    = prices.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _fetch_close(ticker: str, years: int) -> pd.Series:
    """Return a timezone-naive Close price Series for ticker over the last N years."""
    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=years * 365 + 90)
    t  = yf.Ticker(ticker)
    df = t.history(start=start_dt, end=end_dt)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No price data found for {ticker}.")
    close = df["Close"].copy()
    if hasattr(close.index, "tz") and close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    return close


def _has_full_access(user: BetaUser) -> bool:
    if user.is_admin or user.plan in ("PRO", "ELITE"):
        return True
    if user.trial_ends_at and datetime.utcnow() < user.trial_ends_at:
        return True
    return False


# ── Holdings endpoints ─────────────────────────────────────────────────────────

@router.get("/portfolio")
def get_portfolio(
    current_user: BetaUser = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    holdings_db = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.user_id == current_user.id)
        .order_by(PortfolioHolding.added_at.desc())
        .all()
    )
    holdings      = [_holding_with_price(h) for h in holdings_db]
    total_cost    = sum(h["cost_basis"]    for h in holdings)
    total_value   = sum(h["current_value"] for h in holdings if h["current_value"] is not None)
    total_pnl     = round(total_value - total_cost, 4) if total_value else None
    total_pnl_pct = round((total_pnl / total_cost) * 100, 2) if total_pnl is not None and total_cost else None

    return {
        "holdings": holdings,
        "summary": {
            "total_cost":    round(total_cost, 4),
            "total_value":   round(total_value, 4),
            "total_pnl":     total_pnl,
            "total_pnl_pct": total_pnl_pct,
        },
    }


@router.post("/portfolio")
def add_holding(
    body: AddHoldingRequest,
    current_user: BetaUser = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0.")
    if body.avg_buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = body.ticker.upper().strip()

    existing = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.user_id == current_user.id, PortfolioHolding.ticker == ticker)
        .first()
    )
    if existing:
        existing.quantity      = body.quantity
        existing.avg_buy_price = body.avg_buy_price
        existing.currency      = body.currency or "USD"
        db.commit()
        return {"status": "updated", "ticker": ticker}

    is_free = not (current_user.is_admin or current_user.plan in ("PRO", "ELITE"))
    if is_free:
        count = (
            db.query(PortfolioHolding)
            .filter(PortfolioHolding.user_id == current_user.id)
            .count()
        )
        if count >= FREE_HOLDING_LIMIT:
            raise HTTPException(
                status_code=403,
                detail=f"Free plan allows up to {FREE_HOLDING_LIMIT} holdings. Upgrade to Pro for unlimited."
            )

    holding = PortfolioHolding(
        user_id       = current_user.id,
        ticker        = ticker,
        quantity      = body.quantity,
        avg_buy_price = body.avg_buy_price,
        currency      = body.currency or "USD",
    )
    db.add(holding)
    db.commit()
    return {"status": "added", "ticker": ticker}


@router.delete("/portfolio/{holding_id}")
def remove_holding(
    holding_id: int,
    current_user: BetaUser = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    holding = db.query(PortfolioHolding).filter(PortfolioHolding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found.")
    if holding.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your holding.")
    db.delete(holding)
    db.commit()
    return {"status": "removed", "id": holding_id}


# ── Analysis endpoint ──────────────────────────────────────────────────────────

@router.get("/portfolio/analyze")
def analyze_stock(
    ticker: str = Query(..., description="Stock ticker, e.g. AAPL or BTC-USD"),
    years:  int = Query(5, ge=1, le=20, description="Years of history to analyse"),
    current_user: BetaUser = Depends(_get_current_user),
):
    """
    Deep statistical analysis: trend regression, monthly seasonality (t-test),
    MA crossover history, RSI reversal win-rates, and volatility profile.
    """
    if not _has_full_access(current_user):
        raise HTTPException(status_code=403, detail="Portfolio analysis requires a Pro or Elite plan.")

    ticker = ticker.upper().strip()
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    try:
        close = _fetch_close(ticker, years)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch {ticker}: {e}")

    if len(close) < 60:
        raise HTTPException(status_code=400, detail=f"Not enough data for {ticker}. Try a smaller date range or a different ticker.")

    returns_daily = close.pct_change().dropna()

    # ── 1. Trend (linear regression on price) ─────────────────────────────────
    x = np.arange(len(close), dtype=float)
    slope, _intercept, r_value, p_value, _std_err = scipy_stats.linregress(x, close.values.astype(float))

    total_return      = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
    n_years           = max((close.index[-1] - close.index[0]).days / 365.25, 0.01)
    annualized_return = ((1 + total_return / 100) ** (1 / n_years) - 1) * 100

    trend = {
        "direction":             "UPWARD" if slope > 0 else "DOWNWARD",
        "slope_per_day":         round(float(slope), 4),
        "r_squared":             round(float(r_value ** 2), 4),
        "p_value":               round(float(p_value), 6),
        "significant":           bool(p_value < 0.05),
        "total_return_pct":      round(total_return, 2),
        "annualized_return_pct": round(annualized_return, 2),
    }

    # ── 2. Monthly seasonality with t-test significance ────────────────────────
    monthly    = close.resample("ME").last().pct_change().dropna() * 100
    monthly_df = monthly.to_frame("ret")
    monthly_df["month"] = monthly_df.index.month

    seasonality = []
    for m in range(1, 13):
        rets = monthly_df[monthly_df["month"] == m]["ret"].values.astype(float)
        if len(rets) < 2:
            seasonality.append({"month": MONTHS[m-1], "avg_return": None, "win_rate": None, "n": int(len(rets)), "significant": False})
            continue
        avg_ret  = float(np.mean(rets))
        win_rate = float(np.mean(rets > 0) * 100)
        _, p_val = scipy_stats.ttest_1samp(rets, 0)
        seasonality.append({
            "month":       MONTHS[m - 1],
            "avg_return":  round(avg_ret, 2),
            "win_rate":    round(win_rate, 1),
            "n":           int(len(rets)),
            "significant": bool(p_val < 0.10),
        })

    # ── 3. Moving average crossovers (50/200-day) ─────────────────────────────
    ma50  = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    crossovers = []
    prev_above: Optional[bool] = None
    for i in range(200, len(close)):
        above = bool(float(ma50.iloc[i]) > float(ma200.iloc[i]))
        if prev_above is not None and above != prev_above:
            fwd = {}
            for label, days in [("3mo", 63), ("6mo", 126), ("1yr", 252)]:
                fi = i + days
                fwd[label] = round(float((close.iloc[fi] / close.iloc[i] - 1) * 100), 2) if fi < len(close) else None
            crossovers.append({
                "date":       close.index[i].strftime("%Y-%m-%d"),
                "type":       "GOLDEN" if above else "DEATH",
                "price":      round(float(close.iloc[i]), 2),
                "return_3mo": fwd["3mo"],
                "return_6mo": fwd["6mo"],
                "return_1yr": fwd["1yr"],
            })
        prev_above = above

    golden_3mo = [c["return_3mo"] for c in crossovers if c["type"] == "GOLDEN" and c["return_3mo"] is not None]
    death_3mo  = [c["return_3mo"] for c in crossovers if c["type"] == "DEATH"  and c["return_3mo"] is not None]

    above_200 = len(close) >= 200 and float(close.iloc[-1]) > float(ma200.iloc[-1])
    crossover_summary = {
        "golden_cross_count":    len([c for c in crossovers if c["type"] == "GOLDEN"]),
        "death_cross_count":     len([c for c in crossovers if c["type"] == "DEATH"]),
        "golden_avg_3mo_return": round(float(np.mean(golden_3mo)), 2) if golden_3mo else None,
        "golden_win_rate_3mo":   round(float(np.mean([r > 0 for r in golden_3mo]) * 100), 1) if golden_3mo else None,
        "death_avg_3mo_return":  round(float(np.mean(death_3mo)), 2) if death_3mo else None,
        "death_win_rate_3mo":    round(float(np.mean([r > 0 for r in death_3mo]) * 100), 1) if death_3mo else None,
        "current_signal":        ("BULLISH" if above_200 else "BEARISH") if len(close) >= 200 else "INSUFFICIENT_DATA",
    }

    # ── 4. RSI reversal stats ─────────────────────────────────────────────────
    rsi = _compute_rsi(close)

    current_rsi: Optional[float] = None
    for v in reversed(rsi.values):
        if not np.isnan(v):
            current_rsi = round(float(v), 1)
            break

    oversold_fwd: List[float]   = []
    overbought_fwd: List[float] = []
    in_oversold    = False
    in_overbought  = False

    for i in range(14, len(rsi)):
        rv = rsi.iloc[i]
        if np.isnan(rv):
            continue
        rv = float(rv)

        if rv < 30 and not in_oversold:
            in_oversold = True
        elif rv > 35 and in_oversold:
            in_oversold = False
            fi = i + 30
            if fi < len(close):
                oversold_fwd.append(float((close.iloc[fi] / close.iloc[i] - 1) * 100))

        if rv > 70 and not in_overbought:
            in_overbought = True
        elif rv < 65 and in_overbought:
            in_overbought = False
            fi = i + 30
            if fi < len(close):
                overbought_fwd.append(float((close.iloc[fi] / close.iloc[i] - 1) * 100))

    rsi_stats = {
        "current_rsi": current_rsi,
        "oversold": {
            "count":      len(oversold_fwd),
            "avg_return": round(float(np.mean(oversold_fwd)), 2) if oversold_fwd else None,
            "win_rate":   round(float(np.mean([r > 0 for r in oversold_fwd]) * 100), 1) if oversold_fwd else None,
            "max_gain":   round(float(max(oversold_fwd)), 2) if oversold_fwd else None,
            "max_loss":   round(float(min(oversold_fwd)), 2) if oversold_fwd else None,
        },
        "overbought": {
            "count":      len(overbought_fwd),
            "avg_return": round(float(np.mean(overbought_fwd)), 2) if overbought_fwd else None,
            "win_rate":   round(float(np.mean([r > 0 for r in overbought_fwd]) * 100), 1) if overbought_fwd else None,
        },
    }

    # ── 5. Volatility profile ─────────────────────────────────────────────────
    ann_vol = float(returns_daily.std() * np.sqrt(252) * 100)
    yearly  = close.resample("YE").last().pct_change().dropna() * 100

    max_dd_val: Optional[float] = None
    if len(close) > 1:
        roll_max   = close.expanding().max()
        drawdowns  = (close - roll_max) / roll_max * 100
        max_dd_val = round(float(drawdowns.min()), 1)

    sharpe_ratio: Optional[float] = None
    if ann_vol > 0:
        sharpe_ratio = round((annualized_return / 100 - 0.04) / (ann_vol / 100), 2)

    volatility = {
        "annualized_vol":  round(ann_vol, 2),
        "best_year_pct":   round(float(yearly.max()), 1)       if not yearly.empty else None,
        "best_year":       str(yearly.idxmax().year)           if not yearly.empty else None,
        "worst_year_pct":  round(float(yearly.min()), 1)       if not yearly.empty else None,
        "worst_year":      str(yearly.idxmin().year)           if not yearly.empty else None,
        "max_drawdown":    max_dd_val,
        "sharpe_ratio":    sharpe_ratio,
    }

    # ── 6. Plain-English summary ──────────────────────────────────────────────
    sig_months = [s for s in seasonality if s["avg_return"] is not None]
    best_m  = max(sig_months, key=lambda x: x["avg_return"], default=None)
    worst_m = min(sig_months, key=lambda x: x["avg_return"], default=None)

    rsi_note = ""
    if current_rsi is not None:
        if current_rsi < 30:
            rsi_note = f", currently OVERSOLD (RSI {current_rsi})"
        elif current_rsi > 70:
            rsi_note = f", currently OVERBOUGHT (RSI {current_rsi})"
        else:
            rsi_note = f", RSI {current_rsi} (neutral)"

    parts = [
        f"{ticker} returned {total_return:+.1f}% total ({annualized_return:+.1f}%/yr) over {years} year(s).",
        f"Trend: {trend['direction']} — R²={trend['r_squared']}, {'statistically significant (p<0.05)' if trend['significant'] else 'not statistically significant'}.",
        f"Currently {crossover_summary['current_signal']} vs 200-day MA{rsi_note}.",
    ]
    if best_m and worst_m:
        parts.append(
            f"Best month historically: {best_m['month']} (avg {best_m['avg_return']:+.1f}%, {best_m['win_rate']}% win rate). "
            f"Worst: {worst_m['month']} (avg {worst_m['avg_return']:+.1f}%)."
        )
    if crossover_summary["golden_avg_3mo_return"] is not None:
        parts.append(
            f"After {crossover_summary['golden_cross_count']} golden cross(es), avg 3-month return was "
            f"{crossover_summary['golden_avg_3mo_return']:+.1f}% ({crossover_summary['golden_win_rate_3mo']}% win rate)."
        )
    if rsi_stats["oversold"]["count"]:
        parts.append(
            f"After {rsi_stats['oversold']['count']} RSI oversold events, avg 30-day return was "
            f"{rsi_stats['oversold']['avg_return']:+.1f}% ({rsi_stats['oversold']['win_rate']}% win rate)."
        )
    parts.append(
        f"Max drawdown: {max_dd_val}%. Sharpe ratio: {sharpe_ratio}. Annual volatility: {round(ann_vol, 1)}%."
    )

    return {
        "ticker":            ticker,
        "years":             years,
        "current_price":     round(float(close.iloc[-1]), 2),
        "data_from":         close.index[0].strftime("%Y-%m-%d"),
        "data_to":           close.index[-1].strftime("%Y-%m-%d"),
        "trend":             trend,
        "seasonality":       seasonality,
        "crossovers":        crossovers[-12:],
        "crossover_summary": crossover_summary,
        "rsi_stats":         rsi_stats,
        "volatility":        volatility,
        "summary":           " ".join(parts),
    }


# ── Optimize endpoint ──────────────────────────────────────────────────────────

@router.post("/portfolio/optimize")
def optimize_portfolio(
    body: OptimizeRequest,
    current_user: BetaUser = Depends(_get_current_user),
):
    """
    Markowitz mean-variance optimization — maximize Sharpe ratio across provided tickers.
    Returns optimal allocation weights, expected return, volatility, and projected values.
    """
    if not _has_full_access(current_user):
        raise HTTPException(status_code=403, detail="Portfolio optimization requires a Pro or Elite plan.")

    tickers = list({t.upper().strip() for t in body.tickers if t.strip()})
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers.")
    if len(tickers) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 tickers.")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    years = max(1, min(body.years or 5, 20))

    # Fetch price series for each ticker
    price_map: dict = {}
    for t in tickers:
        try:
            close = _fetch_close(t, years)
            if len(close) >= 60:
                price_map[t] = close
        except Exception:
            pass

    if len(price_map) < 2:
        raise HTTPException(status_code=400, detail="Not enough valid price data for 2+ tickers. Check your tickers.")

    valid_tickers = list(price_map.keys())
    data = pd.DataFrame(price_map).dropna()

    if len(data) < 60:
        raise HTTPException(status_code=400, detail="Not enough overlapping price history across tickers.")

    returns = data.pct_change().dropna()
    mu      = returns.mean() * 252          # annualised expected return vector
    cov     = returns.cov() * 252           # annualised covariance matrix
    n       = len(valid_tickers)
    rf      = 0.04                          # 4% risk-free rate

    def neg_sharpe(w: np.ndarray) -> float:
        ret = float(np.dot(w, mu))
        vol = float(np.sqrt(np.dot(w, np.dot(cov.values, w))))
        return -(ret - rf) / vol if vol > 0 else 0.0

    x0          = np.ones(n) / n
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    bounds      = [(0.05, 0.50)] * n
    result      = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    weights     = result.x if result.success else x0

    port_return = float(np.dot(weights, mu))
    port_vol    = float(np.sqrt(np.dot(weights, np.dot(cov.values, weights))))
    port_sharpe = round((port_return - rf) / port_vol, 2) if port_vol > 0 else None

    allocations = []
    for i, t in enumerate(valid_tickers):
        w      = float(weights[i])
        amount = round(body.amount * w, 2)
        exp_r  = round(float(mu.get(t, 0)) * 100, 1)
        vol_t  = round(float(np.sqrt(float(cov.loc[t, t]))) * 100, 1)
        price  = round(float(price_map[t].iloc[-1]), 2)
        shares = round(amount / price, 4) if price > 0 else None
        allocations.append({
            "ticker":              t,
            "weight_pct":          round(w * 100, 1),
            "amount":              amount,
            "shares":              shares,
            "current_price":       price,
            "expected_return_pct": exp_r,
            "volatility_pct":      vol_t,
        })
    allocations.sort(key=lambda x: x["weight_pct"], reverse=True)

    return {
        "tickers":     valid_tickers,
        "amount":      body.amount,
        "years":       years,
        "allocations": allocations,
        "portfolio": {
            "expected_return_pct":  round(port_return * 100, 1),
            "volatility_pct":       round(port_vol * 100, 1),
            "sharpe_ratio":         port_sharpe,
            "expected_value_low":   round(body.amount * (1 + port_return - port_vol), 2),
            "expected_value_mid":   round(body.amount * (1 + port_return), 2),
            "expected_value_high":  round(body.amount * (1 + port_return + port_vol), 2),
        },
        "note": "Based on historical data only. Past performance does not guarantee future results. Not financial advice.",
    }
