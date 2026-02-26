from sqlalchemy import create_engine, Column, Integer, Text, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finsight.db")

# Neon/Render PostgreSQL uses "postgres://" but SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False; PostgreSQL does not
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Signal(Base):
    __tablename__ = "signals"

    id             = Column(Integer, primary_key=True, index=True)
    news_hash      = Column(Text, unique=True, nullable=False, index=True)
    title          = Column(Text, nullable=False)
    source         = Column(Text, nullable=False)
    source_domain  = Column(Text, nullable=False)
    credibility    = Column(Float, nullable=False)
    published_at   = Column(DateTime, nullable=False)
    ingested_at    = Column(DateTime, default=datetime.utcnow)
    signal         = Column(Text, nullable=False)   # BUY / SELL / AVOID / WATCH
    confidence     = Column(Float, nullable=False)
    impact         = Column(Float, nullable=False)  # -1.0 to +1.0
    tickers        = Column(Text, nullable=False)   # JSON-encoded list
    market         = Column(Text, nullable=False)   # ASX / US / CRYPTO / COMMODITY
    summary        = Column(Text, nullable=False)
    reasoning      = Column(Text, nullable=False)
    signal_logic   = Column(Text, nullable=True)   # "cut losses — more downside" / "take profits" / "buy the dip" etc.
    pump_dump_risk = Column(Text, nullable=True, default="LOW")  # LOW / MEDIUM / HIGH
    is_twitter     = Column(Boolean, default=False)
    twitter_handle = Column(Text, nullable=True)
    is_active      = Column(Boolean, default=True)


class Price(Base):
    __tablename__ = "prices"

    id          = Column(Integer, primary_key=True, index=True)
    ticker      = Column(Text, nullable=False, index=True)
    name        = Column(Text, nullable=True)
    price       = Column(Float, nullable=False)
    change_pct  = Column(Float, nullable=False)
    currency    = Column(Text, default="USD")
    fetched_at  = Column(DateTime, default=datetime.utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id       = Column(Integer, primary_key=True, index=True)
    ticker   = Column(Text, unique=True, nullable=False)
    name     = Column(Text, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(Text, nullable=False, index=True)
    code       = Column(Text, nullable=False)
    name       = Column(Text, nullable=False)
    plan       = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False)


class BetaUser(Base):
    __tablename__ = "beta_users"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(Text, nullable=False)
    email       = Column(Text, nullable=False, unique=True, index=True)
    plan        = Column(Text, nullable=False, default="PRO")   # PRO or ELITE
    signed_up_at = Column(DateTime, default=datetime.utcnow)


class ChartSnapshot(Base):
    __tablename__ = "chart_snapshots"

    id            = Column(Integer, primary_key=True, index=True)
    snapshot_hour = Column(Text, nullable=False)
    buy_count     = Column(Integer, default=0)
    sell_count    = Column(Integer, default=0)
    avoid_count   = Column(Integer, default=0)
    watch_count   = Column(Integer, default=0)
    recorded_at   = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
