import random
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db, BetaUser, OtpCode
from config import settings

log    = logging.getLogger(__name__)
router = APIRouter()


class BetaSignupRequest(BaseModel):
    name:  str
    email: EmailStr
    plan:  str = "PRO"


class BetaVerifyRequest(BaseModel):
    email: EmailStr
    code:  str


def _send_otp_email(to_email: str, name: str, code: str, plan: str):
    """Send OTP via Gmail SMTP. Falls back to logging if credentials not set."""
    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        log.warning(f"[OTP] No Gmail credentials set. Code for {to_email}: {code}")
        return

    html = f"""
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
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your FinSight verification code"
        msg["From"]    = f"FinSight <{settings.GMAIL_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())

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

    # Mark OTP as used
    otp.used = True
    db.commit()

    # Save or update BetaUser
    existing = db.query(BetaUser).filter(BetaUser.email == email).first()
    if existing:
        existing.plan = otp.plan
        db.commit()
        return {"status": "ok", "plan": existing.plan, "already_registered": True}

    user = BetaUser(name=otp.name, email=email, plan=otp.plan, signed_up_at=datetime.utcnow())
    db.add(user)
    db.commit()
    return {"status": "ok", "plan": otp.plan, "already_registered": False}


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
