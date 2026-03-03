"""
Auth router — login, OTP password reset, set-password, /me, admin bootstrap.
"""
import random
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext

from database import get_db, BetaUser, OtpCode
from config import settings
from routers.beta import _send_otp_email

log    = logging.getLogger(__name__)
router = APIRouter()

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prep_pw(password: str) -> str:
    """SHA-256 the password before bcrypt — avoids bcrypt's 72-byte hard limit."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_token(user: BetaUser) -> str:
    payload = {
        "sub":               user.email,
        "name":              user.name,
        "plan":              user.plan,
        "trial_ends_at":     user.trial_ends_at.isoformat()  if user.trial_ends_at     else None,
        "access_expires_at": user.access_expires_at.isoformat() if user.access_expires_at else None,
        "is_admin":          user.is_admin,
        "exp":               datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> BetaUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        email   = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(BetaUser).filter(BetaUser.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class RequestOtpRequest(BaseModel):
    email: EmailStr


class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    code:  str


class SetPasswordRequest(BaseModel):
    password:    str
    reset_token: Optional[str] = None   # provided when coming from OTP reset flow


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Email + password → JWT."""
    email = payload.email.lower().strip()
    user  = db.query(BetaUser).filter(BetaUser.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="No account found for that email. Please sign up first.")

    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Password not set yet. Use 'Forgot password' to receive an OTP and set one."
        )

    if not pwd_ctx.verify(_prep_pw(payload.password), user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password.")

    return {"status": "ok", "token": _make_token(user), "plan": user.plan}


@router.post("/login/request-otp")
def request_reset_otp(payload: RequestOtpRequest, db: Session = Depends(get_db)):
    """Send OTP for password reset (or first-time password setup)."""
    email = payload.email.lower().strip()
    user  = db.query(BetaUser).filter(BetaUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found for that email.")

    code       = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Reuse OtpCode table with plan="RESET" to distinguish
    db.query(OtpCode).filter(OtpCode.email == email, OtpCode.used == False).delete()
    db.commit()

    otp = OtpCode(email=email, code=code, name=user.name, plan="RESET", expires_at=expires_at)
    db.add(otp)
    db.commit()

    _send_otp_email(email, user.name, code, "password reset")
    return {"status": "otp_sent", "message": "Verification code sent to your email."}


@router.post("/login/verify-otp")
def verify_reset_otp(payload: VerifyResetOtpRequest, db: Session = Depends(get_db)):
    """Verify OTP → return a short-lived reset token to use with set-password."""
    email = payload.email.lower().strip()
    otp   = (
        db.query(OtpCode)
        .filter(OtpCode.email == email, OtpCode.plan == "RESET", OtpCode.used == False)
        .order_by(OtpCode.expires_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(status_code=400, detail="No reset code found. Please request a new one.")
    if datetime.utcnow() > otp.expires_at:
        raise HTTPException(status_code=400, detail="Code expired. Please request a new one.")
    if otp.code != payload.code.strip():
        raise HTTPException(status_code=400, detail="Incorrect code.")

    otp.used = True
    db.commit()

    # Issue a short-lived reset token (10 min)
    reset_payload = {
        "sub":   email,
        "scope": "password_reset",
        "exp":   datetime.utcnow() + timedelta(minutes=10),
    }
    reset_token = jwt.encode(reset_payload, settings.JWT_SECRET, algorithm="HS256")
    return {"status": "ok", "reset_token": reset_token}


@router.post("/login/set-password")
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db),
                 authorization: Optional[str] = Header(None)):
    """Set or update password. Requires either a reset_token or an active session."""
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    # Determine who is setting the password
    email = None

    if payload.reset_token:
        try:
            data  = jwt.decode(payload.reset_token, settings.JWT_SECRET, algorithms=["HS256"])
            scope = data.get("scope")
            email = data.get("sub")
            if scope != "password_reset":
                raise HTTPException(status_code=400, detail="Invalid reset token.")
        except JWTError:
            raise HTTPException(status_code=400, detail="Reset token invalid or expired.")
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            data  = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            email = data.get("sub")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid session token.")
    else:
        raise HTTPException(status_code=401, detail="Reset token or active session required.")

    user = db.query(BetaUser).filter(BetaUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = pwd_ctx.hash(_prep_pw(payload.password))
    db.commit()

    return {"status": "ok", "token": _make_token(user), "message": "Password set. You are now logged in."}


@router.get("/me")
def me(current_user: BetaUser = Depends(_get_current_user)):
    """Return current user details from JWT."""
    return {
        "email":              current_user.email,
        "name":               current_user.name,
        "plan":               current_user.plan,
        "trial_ends_at":      current_user.trial_ends_at.isoformat()     if current_user.trial_ends_at     else None,
        "access_expires_at":  current_user.access_expires_at.isoformat() if current_user.access_expires_at else None,
        "is_admin":           current_user.is_admin,
    }


@router.post("/admin/bootstrap")
def admin_bootstrap(db: Session = Depends(get_db)):
    """One-time: set wagle.sadi@gmail.com as admin. Safe to call multiple times."""
    user = db.query(BetaUser).filter(BetaUser.email == "wagle.sadi@gmail.com").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Sign up first.")
    user.is_admin = True
    db.commit()
    return {"status": "ok", "message": f"{user.email} is now admin."}
