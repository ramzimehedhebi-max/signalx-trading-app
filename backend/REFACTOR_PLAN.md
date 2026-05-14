# Backend Refactoring Plan (P3) — Status Report

## ✅ COMPLETED (this session)

### Foundation Modules Created (ready to use)

#### `/app/backend/core/__init__.py`
Shared infrastructure used everywhere:
- `db` and `client` (Motor singleton — same instance as `server.py` currently has)
- `BINANCE_BASE`, `JWT_SECRET`, `JWT_ALG`, `JWT_EXPIRE_MINUTES`, `EMERGENT_LLM_KEY` constants
- `bearer` HTTPBearer dependency
- `hash_password(pw)`, `verify_password(pw, hashed)`
- `create_token(user_id)`
- `get_current_user(creds)` — FastAPI Depends

#### `/app/backend/models/__init__.py`
All Pydantic models in one tidy file (12 KB):
- Auth: `RegisterReq`, `LoginReq`, `UserPublic`, `AuthResp`, `ForgotPasswordReq`, `ResetPasswordReq`, `PushTokenReq`
- Watchlist/Alerts: `WatchlistItem`, `AddWatchReq`, `AlertCreateReq`, `Alert`
- Portfolio: `PositionCreateReq`, `Position`
- Signal: `SignalReq`, `SignalResp`
- Binance: `BinanceConnectReq`
- Premium: `PremiumCheckoutReq`
- Predict: `PredictReq`
- Backtest: `BacktestReq`
- Bot: `BotConfig`, `BotConfigUpdate`, `BotPosition`, `BotTrade` (includes all 9 advanced-feature fields)

### Empty packages prepared:
- `/app/backend/services/__init__.py`
- `/app/backend/routes/__init__.py`

---

## 📋 REMAINING WORK (next dedicated session, 60-90 min)

### Step 1: Extract Services (~1200 lines moved)

Create these service modules with code MOVED from `server.py`:

| Module | Responsibilities | Approx. lines |
|---|---|---|
| `services/notifications.py` | `_send_push`, `_create_notification` | ~50 |
| `services/binance_helpers.py` | `_get_user_binance` | ~20 |
| `services/premium.py` | `_get_premium_status` | ~30 |
| `services/indicators.py` | `compute_sma`, `compute_ema`, `compute_rsi`, `_eval_signal` | ~70 |
| `services/ai.py` | `_claude_validate`, `_get_cached_prediction`, `_fetch_or_compute_prediction` | ~140 |
| `services/bot_engine.py` | `SYMBOL_CATEGORIES`, `get_category`, `symbolToBase_py`, `_get_or_create_bot_config`, `_close_position`, `_close_position_partial`, `_bot_check_positions`, `_bot_evaluate_entries` | ~700 |
| `services/bot_loop.py` | `_bot_loop`, `_start_bot` background task | ~40 |

### Step 2: Extract Routes (~1100 lines moved)

Create routers using `APIRouter()` and `@router.get(...)`:

| Module | Endpoints | Approx. lines |
|---|---|---|
| `routes/auth.py` | register, login, me, forgot-password, reset-password | ~140 |
| `routes/market.py` | tickers, ticker, klines | ~90 |
| `routes/signals.py` | generate-signal, recent-signals | ~140 |
| `routes/watchlist.py` | watchlist + alerts CRUD | ~50 |
| `routes/portfolio.py` | portfolio CRUD | ~70 |
| `routes/notifications.py` | push-token, notifications list/read | ~30 |
| `routes/binance.py` | connect, disconnect, status, account | ~120 |
| `routes/premium.py` | status, checkout, cancel, stripe return, webhook | ~200 |
| `routes/bot.py` | bot config + positions + trades + stats + run-now | ~170 |
| `routes/backtest.py` | bot backtest endpoint | ~210 |
| `routes/predict.py` | ai-predict + predict-top | ~190 |

### Step 3: Slim `server.py` to ~80 lines

Replace current `server.py` content with:
```python
"""Crypto Signals API — thin entry point."""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import logging

from core import db, client
from services.bot_loop import start_bot

# Routers (each defines its own APIRouter)
from routes import auth, market, signals, watchlist, portfolio
from routes import notifications, binance, premium, bot, backtest, predict

app = FastAPI(title="Crypto Signals API")
api_router = APIRouter(prefix="/api")

# Mount routers
for r in [auth.router, market.router, signals.router, watchlist.router, portfolio.router,
          notifications.router, binance.router, premium.router, bot.router,
          backtest.router, predict.router]:
    api_router.include_router(r)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/api/")
async def root():
    return {"name": "Crypto Signals API", "version": "1.0"}

@app.on_event("startup")
async def startup_event():
    await start_bot()

@app.on_event("shutdown")
async def shutdown_event():
    client.close()
```

---

## 🧪 Validation Protocol (per step)

After each service/route extraction:
1. Restart backend: `sudo supervisorctl restart backend`
2. Verify: `curl -s http://localhost:8001/api/ | python3 -m json.tool`
3. Re-run: `python3 /app/backend_test.py` — all 19 tests must pass
4. If broken, `git checkout backend/server.py backend/services/X.py` and try again

---

## ⚠️ Risk Notes

- **Circular imports**: `bot_engine.py` needs `ai.py` (for `_fetch_or_compute_prediction`),
  `binance_helpers.py` (for `_get_user_binance`), `notifications.py` (for `_create_notification`),
  `premium.py` should NOT depend on bot_engine. Strict dependency: routes→services→core→models.
- **`db` shared singleton**: ALL modules import `db` from `core`. Never create a second Mongo client.
- **Bot loop**: starts on FastAPI `startup` event. Don't break this — it powers paper + live trading.
- **Pydantic models**: Already extracted to `models/`. Just update imports in services/routes.
