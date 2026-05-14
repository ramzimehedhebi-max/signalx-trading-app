# Backend Architecture (Post-Refactor)

```
/app/backend/
├── server.py                  60 lines · FastAPI app + CORS + router includes + lifespan
├── core/__init__.py           DB singleton, JWT helpers, env constants, get_current_user
├── models/__init__.py         All Pydantic models (Auth/Bot/Market/Premium/Signal/…)
├── services/
│   ├── ai.py                  Claude integration: validation + predictions caching
│   ├── binance_helpers.py     _get_user_binance (returns authenticated BinanceClient)
│   ├── bot_engine.py          Core bot logic: categorization, close, partial-close,
│   │                          check positions (TP/SL/Trailing TP/Partial), evaluate entries
│   ├── bot_loop.py            Background asyncio loop + start_bot()
│   ├── indicators.py          SMA/EMA/RSI + _eval_signal
│   ├── notifications.py       _send_push + _create_notification
│   └── premium_svc.py         _get_premium_status (Stripe-backed)
├── routes/
│   ├── auth.py                /auth/register · /auth/login · /auth/me ·
│   │                          /auth/forgot-password · /auth/reset-password
│   ├── market.py              /market/tickers · /market/ticker · /market/klines
│   ├── signals.py             /generate-signal · /signals/recent
│   ├── watchlist.py           /watchlist · /alerts
│   ├── portfolio.py           /portfolio
│   ├── notifications.py       /push-token · /notifications · /notifications/{id}/read
│   ├── binance.py             /binance/connect · /binance/disconnect · /binance/status ·
│   │                          /binance/account
│   ├── premium.py             /premium/status · /premium/checkout · /premium/cancel ·
│   │                          /stripe/return · /stripe/webhook
│   ├── bot.py                 /bot/config · /bot/positions · /bot/trades · /bot/stats ·
│   │                          /bot/run-now · /bot/analytics · /bot/reset
│   ├── backtest.py            /bot/backtest
│   └── predict.py             /ai/predict · /ai/predict/top
├── binance_live.py            (unchanged) BinanceClient + AES key encryption
├── email_service.py           (unchanged) Resend email integration
└── stripe_subs.py             (unchanged) Stripe customer + checkout + webhook helpers
```

## Dependency layering (no cycles)

```
routes → services → core
       ↘ models ↗
```

- Routes import: `core`, `models`, `services.<module>`
- Services import: `core`, `models`, sometimes other `services.<module>` (one-way)
- `core` imports nothing from routes/services/models
- `models` imports nothing from routes/services/core

## Stats

| Before | After |
|---|---|
| 2838 lines in `server.py` | 60 lines in `server.py` |
| 1 file | 19 files in 4 packages |
| Hard to navigate | Each domain isolated |

## How to add a new endpoint

1. Pick / create the right router in `routes/<domain>.py`
2. Add Pydantic models in `models/__init__.py` (or split when it gets big)
3. Add business logic to `services/<domain>.py` if non-trivial
4. The router is auto-mounted on `/api` via `server.py`

## How to test

```bash
sudo supervisorctl restart backend
python3 /app/backend_test.py    # 19 tests covering advanced bot features
```
