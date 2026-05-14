"""All Pydantic models grouped by domain (kept in one file for simplicity)."""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
import uuid


# ============ AUTH ============
class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime


class AuthResp(BaseModel):
    token: str
    user: UserPublic


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class PushTokenReq(BaseModel):
    token: str


# ============ WATCHLIST / ALERTS ============
class WatchlistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AddWatchReq(BaseModel):
    symbol: str


class AlertCreateReq(BaseModel):
    symbol: str
    target_price: float
    direction: str  # "above" or "below"


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    target_price: float
    direction: str
    triggered: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============ PORTFOLIO ============
class PositionCreateReq(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    side: str = "long"


class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    quantity: float
    entry_price: float
    side: str = "long"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============ SIGNAL ============
class SignalReq(BaseModel):
    symbol: str
    interval: str = "1h"


class SignalResp(BaseModel):
    symbol: str
    interval: str
    action: str  # BUY / SELL / HOLD
    confidence: int
    entry: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    timeframe: str
    reasoning: str
    indicators: dict
    generated_at: datetime


# ============ BINANCE ============
class BinanceConnectReq(BaseModel):
    api_key: str
    api_secret: str


# ============ PREMIUM ============
class PremiumCheckoutReq(BaseModel):
    return_url: Optional[str] = None


# ============ PREDICT ============
class PredictReq(BaseModel):
    symbol: str
    horizon: str = "24h"  # 24h / 3d / 7d


# ============ BACKTEST ============
class BacktestReq(BaseModel):
    days: int = 30


# ============ BOT ============
# Default pairs for a new user's bot (must match services/bot_engine.DEFAULT_BOT_PAIRS)
_DEFAULT_BOT_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "MATICUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT",
]


class BotConfig(BaseModel):
    user_id: str
    enabled: bool = False
    mode: str = "paper"
    strategy: str = "hybrid"
    capital_usdt: float = 1000.0
    paper_balance_usdt: float = 1000.0
    max_positions: int = 5
    position_size_pct: float = 25.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 10.0
    interval_minutes: int = 5
    trailing_enabled: bool = True
    trailing_trigger_pct: float = 3.0
    trailing_distance_pct: float = 2.0
    compounding_enabled: bool = True
    ai_predictions_enabled: bool = True
    ai_exit_confidence: int = 65
    # Advanced features
    diversification_enabled: bool = True
    max_per_category: int = 2
    tp_trailing_enabled: bool = True
    tp_trail_distance_pct: float = 1.5
    partial_tp_enabled: bool = True
    partial_tp_level1_pct: float = 3.0
    partial_tp_level1_close: float = 50.0
    partial_tp_level2_pct: float = 6.0
    partial_tp_level2_close: float = 30.0
    # Live trading
    live_mode: bool = False
    live_max_position_usdt: float = 50.0
    live_killswitch: bool = False
    pairs: List[str] = Field(default_factory=lambda: _DEFAULT_BOT_PAIRS.copy())
    last_run_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BotConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    capital_usdt: Optional[float] = None
    max_positions: Optional[int] = None
    position_size_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    interval_minutes: Optional[int] = None
    pairs: Optional[List[str]] = None
    strategy: Optional[str] = None
    trailing_enabled: Optional[bool] = None
    trailing_trigger_pct: Optional[float] = None
    trailing_distance_pct: Optional[float] = None
    compounding_enabled: Optional[bool] = None
    ai_predictions_enabled: Optional[bool] = None
    ai_exit_confidence: Optional[int] = None
    diversification_enabled: Optional[bool] = None
    max_per_category: Optional[int] = None
    tp_trailing_enabled: Optional[bool] = None
    tp_trail_distance_pct: Optional[float] = None
    partial_tp_enabled: Optional[bool] = None
    partial_tp_level1_pct: Optional[float] = None
    partial_tp_level1_close: Optional[float] = None
    partial_tp_level2_pct: Optional[float] = None
    partial_tp_level2_close: Optional[float] = None
    live_mode: Optional[bool] = None
    live_max_position_usdt: Optional[float] = None
    live_killswitch: Optional[bool] = None


class BotPosition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    side: str = "long"
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    original_stop_loss: float = 0.0
    highest_price: float = 0.0
    trail_active: bool = False
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_reason: str = ""
    ai_target_median: Optional[float] = None
    last_ai_check: Optional[datetime] = None
    status: str = "open"
    category: str = "Other"
    original_quantity: float = 0.0
    tp_trail_active: bool = False
    partial_tp_done: List[int] = Field(default_factory=list)


class BotTrade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pnl: float
    pnl_pct: float
    exit_reason: str
