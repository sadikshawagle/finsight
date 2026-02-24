from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, ChartSnapshot

router = APIRouter()


@router.get("/chart-data")
def get_chart_data(db: Session = Depends(get_db)):
    """Return signal activity by hour for the chart tab."""
    snapshots = db.query(ChartSnapshot).order_by(
        ChartSnapshot.recorded_at.asc()
    ).limit(24).all()

    if not snapshots:
        # Return empty placeholder so the chart doesn't crash
        return [{"time": "Now", "buy": 0, "sell": 0, "avoid": 0, "watch": 0}]

    return [
        {
            "time":  s.snapshot_hour,
            "buy":   s.buy_count,
            "sell":  s.sell_count,
            "avoid": s.avoid_count,
            "watch": s.watch_count,
        }
        for s in snapshots
    ]
