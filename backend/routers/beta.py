import random
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from database import get_db, BetaUser, OtpCode
from config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

log    = logging.getLogger(__name__)
router = APIRouter()


class BetaSignupRequest(BaseModel):
    name:  str
    email: EmailStr
    plan:  str = "PRO"


class BetaVerifyRequest(BaseModel):
    email:    EmailStr
    code:     str
    password: Optional[str] = None  # set during signup form; hashed + stored on verify


def _send_otp_email(to_email: str, name: str, code: str, plan: str):
    """Send OTP via Resend. Falls back to logging if key not set."""
    if not settings.RESEND_API_KEY:
        log.warning(f"[OTP] No RESEND_API_KEY set. Code for {to_email}: {code}")
        return

    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from":    settings.RESEND_FROM,
            "to":      [to_email],
            "subject": "Your FinSight verification code",
            "html":    f"""
                <div style="font-family:monospace;background:#0d1117;color:#e6edf3;padding:32px;border-radius:12px;max-width:480px">
                  <h2 style="color:#4ade80;margin-bottom:8px">FinSight</h2>
                  <p>Hi {name},</p>
                  <p>Your verification code for <strong>{plan}</strong> access is:</p>
                  <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;text-align:center;margin:20px 0">
                    <span style="font-size:36px;font-weight:900;letter-spacing:0.3em;color:#4ade80">{code}</span>
                  </div>
                  <p style="color:#6b7280;font-size:12px">This code expires in 10 minutes. Do not share it with anyone.</p>
                  <p style="color:#374151;font-size:11px">Not financial advice. FinSight is an informational tool only.</p>
                </div>
            """,
        })
        log.info(f"OTP email sent to {to_email}")
    except Exception as e:
        log.error(f"Failed to send OTP email to {to_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")


@router.post("/beta-signup")
def beta_signup(payload: BetaSignupRequest, db: Session = Depends(get_db)):
    """Step 1: validate email, generate OTP, send verification email."""
    plan  = payload.plan.upper()
    if plan not in {"PRO", "ELITE"}:
        plan = "PRO"

    email = payload.email.lower().strip()
    name  = payload.name.strip()

    # Generate 6-digit OTP
    code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Invalidate any previous unused OTPs for this email
    db.query(OtpCode).filter(OtpCode.email == email, OtpCode.used == False).delete()
    db.commit()

    otp = OtpCode(email=email, code=code, name=name, plan=plan, expires_at=expires_at)
    db.add(otp)
    db.commit()

    _send_otp_email(email, name, code, plan)

    return {"status": "otp_sent", "message": "Verification code sent to your email."}


@router.post("/beta-verify")
def beta_verify(payload: BetaVerifyRequest, db: Session = Depends(get_db)):
    """Step 2: verify OTP code → unlock plan."""
    email = payload.email.lower().strip()

    otp = (
        db.query(OtpCode)
        .filter(OtpCode.email == email, OtpCode.used == False)
        .order_by(OtpCode.expires_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(status_code=400, detail="No verification code found. Please request a new one.")

    if datetime.utcnow() > otp.expires_at:
        raise HTTPException(status_code=400, detail="Code expired. Please request a new one.")

    if otp.code != payload.code.strip():
        raise HTTPException(status_code=400, detail="Incorrect code. Please try again.")

    # Hash password if provided
    try:
        pw_hash = pwd_ctx.hash(payload.password) if payload.password and len(payload.password) >= 8 else None
    except Exception as e:
        log.error(f"Password hashing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Password hashing failed: {str(e)}")

    # Save or update BetaUser FIRST, then mark OTP as used — all in one commit
    try:
        existing = db.query(BetaUser).filter(BetaUser.email == email).first()
        if existing:
            existing.plan = otp.plan
            if pw_hash:
                existing.password_hash = pw_hash
            otp.used = True
            db.commit()
            token = _issue_token(existing)
            return {"status": "ok", "plan": existing.plan, "already_registered": True, "token": token}

        now  = datetime.utcnow()
        user = BetaUser(
            name          = otp.name,
            email         = email,
            plan          = otp.plan,
            signed_up_at  = now,
            trial_ends_at = now + timedelta(days=30),
            password_hash = pw_hash,
        )
        db.add(user)
        otp.used = True
        db.commit()
        token = _issue_token(user)
        return {"status": "ok", "plan": otp.plan, "already_registered": False, "token": token}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"beta_verify user creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Account creation failed: {str(e)}")


def _issue_token(user: BetaUser) -> str:
    payload = {
        "sub":               user.email,
        "name":              user.name,
        "plan":              user.plan,
        "trial_ends_at":     user.trial_ends_at.isoformat()     if user.trial_ends_at     else None,
        "access_expires_at": user.access_expires_at.isoformat() if user.access_expires_at else None,
        "is_admin":          user.is_admin,
        "exp":               datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


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
