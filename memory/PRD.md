# SignalX — Crypto Trading Signals (Binance + AI)

## Vision
French mobile app that tells users **when to buy and sell** crypto on Binance using real-time market data and AI-powered analysis (Claude Sonnet 4.5).

## MVP Features (delivered)
- **Auth**: JWT register/login/logout (email + password), session persisted via AsyncStorage
- **Markets**: Top 20 USDT pairs from Binance (data-api.binance.vision), sortable by volume / gainers / losers / favorites; per-symbol star toggle
- **Watchlist**: persisted per-user, horizontal scroll cards on dashboard, manage from Markets
- **Coin Detail**: live price, 24h high/low/volume, custom SVG candlestick chart with interval selector (15m / 1h / 4h / 1J / 1S), one-tap AI signal
- **AI Signals (core)**: POST /api/ai/signal — Claude Sonnet 4.5 analyzes RSI(14), SMA20/50, EMA12/26, 50-period range and returns BUY / SELL / HOLD with confidence %, entry, target, stop-loss, French reasoning, and timeframe; recent signals history
- **Portfolio**: track positions (symbol, quantity, entry price), live P&L $ and % using Binance current prices
- **Profile**: avatar, settings list, French disclaimer about trading risks, logout

## Stack
- Backend: FastAPI + Motor (MongoDB) + emergentintegrations (LiteLLM Claude) + httpx
- Frontend: Expo Router + React Native + react-native-svg (custom charts) + AsyncStorage + expo-haptics
- Theme: Dark "Jewel/Luxury" palette (#090C15 bg, #F3BA2F Binance yellow, #00E396 / #FF4560 buy/sell)

## Backend Routes (all under /api)
- POST /auth/register, POST /auth/login, GET /auth/me
- GET /market/tickers, GET /market/ticker/{symbol}, GET /market/klines/{symbol}
- POST /ai/signal, GET /ai/signals/recent
- GET/POST/DELETE /watchlist
- GET/POST/DELETE /alerts
- GET/POST/DELETE /portfolio

## Bot IA — Trading automatique (paper) — V2
- Onglet dédié "Bot IA" remplace "Portefeuille"
- Toggle ON/OFF, scanner toutes les 5 min en arrière-plan + bouton "Forcer un scan"
- Stratégie hybride : RSI(14) + EMA12/EMA26 → si signal force ≥ 70 ouverture auto, sinon validation Claude Sonnet 4.5
- Paramétrable : capital virtuel, taille position %, max positions simultanées, SL %, TP %, paires à trader
- Stop-loss et take-profit auto-déclenchés sur cycle 60s
- Endpoints: GET/PUT /api/bot/config, GET /api/bot/positions, GET /api/bot/trades, GET /api/bot/stats, POST /api/bot/reset, POST /api/bot/run-now
- Stats UI : balance paper USDT, P&L total, win rate, positions ouvertes vs max, historique des trades

## Future Enhancements
- Push notifications for price alerts (Expo Notifications)
- WebSocket live ticker stream for the coin detail screen
- Multi-timeframe consensus (1h + 4h + 1d simultaneously) for stronger signals
- Subscription tier (Stripe) — unlock Pro signals + smart alerts (revenue model)
- Backtest module: simulate AI signals over historical data
- Social proof: shareable signal cards
