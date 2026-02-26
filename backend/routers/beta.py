from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db, BetaUser
from datetime import datetime

router = APIRouter()


class BetaSignupRequest(BaseModel):
    name:  str
    email: EmailStr
    plan:  str = "PRO"


@router.post("/beta-signup")
def beta_signup(payload: BetaSignupRequest, db: Session = Depends(get_db)):
    plan = payload.plan.upper()
    if plan not in {"PRO", "ELITE"}:
        plan = "PRO"

    # If email already signed up, just return success (idempotent)
    existing = db.query(BetaUser).filter(BetaUser.email == payload.email.lower().strip()).first()
    if existing:
        existing.plan = plan  # upgrade plan if they pick ELITE second time
        db.commit()
        return {"status": "ok", "plan": existing.plan, "already_registered": True}

    user = BetaUser(
        name         = payload.name.strip(),
        email        = payload.email.lower().strip(),
        plan         = plan,
        signed_up_at = datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    return {"status": "ok", "plan": plan, "already_registered": False}


@router.get("/beta-users")
def list_beta_users(db: Session = Depends(get_db)):
    """Admin endpoint to see who has signed up."""
    users = db.query(BetaUser).order_by(BetaUser.signed_up_at.desc()).all()
    return [
        {
            "id":           u.id,
            "name":         u.name,
            "email":        u.email,
            "plan":         u.plan,
            "signed_up_at": u.signed_up_at.isoformat() if u.signed_up_at else None,
        }
        for u in users
    ]
