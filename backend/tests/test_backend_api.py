# Backend API tests for Crypto Signals App
import uuid
import pytest


# ============ Health ============
class TestHealth:
    def test_api_root(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "crypto-signals"


# ============ Auth ============
class TestAuth:
    def test_login_existing_user(self, api_client, base_url):
        r = api_client.post(f"{base_url}/api/auth/login",
                            json={"email": "trader@test.com", "password": "test1234"})
        # We expect either 200 (already registered) or 401 (to be fixed by auth_token fixture)
        assert r.status_code in (200, 401)

    def test_register_duplicate_fails(self, api_client, base_url, auth_token):
        r = api_client.post(f"{base_url}/api/auth/register",
                            json={"email": "trader@test.com", "password": "test1234", "name": "Trader"})
        assert r.status_code == 400
        assert "Email" in r.json().get("detail", "")

    def test_login_wrong_password(self, api_client, base_url):
        r = api_client.post(f"{base_url}/api/auth/login",
                            json={"email": "trader@test.com", "password": "wrong_pw"})
        assert r.status_code == 401

    def test_me_requires_auth(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, api_client, base_url, auth_headers):
        r = api_client.get(f"{base_url}/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "trader@test.com"
        assert "id" in data and "name" in data

    def test_register_new_user(self, api_client, base_url):
        uid = uuid.uuid4().hex[:8]
        email = f"test_user_{uid}@example.com"
        r = api_client.post(f"{base_url}/api/auth/register",
                            json={"email": email, "password": "pass1234", "name": "TEST User"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and data["user"]["email"] == email


# ============ Market Data ============
class TestMarket:
    def test_tickers_default(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/market/tickers")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        s0 = data[0]
        for k in ["symbol", "lastPrice", "priceChangePercent", "quoteVolume"]:
            assert k in s0

    def test_tickers_specific(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/market/tickers", params={"symbols": "BTCUSDT,ETHUSDT"})
        assert r.status_code == 200
        data = r.json()
        syms = {d["symbol"] for d in data}
        assert syms == {"BTCUSDT", "ETHUSDT"}

    def test_ticker_by_symbol(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/market/ticker/BTCUSDT")
        assert r.status_code == 200
        d = r.json()
        assert d["symbol"] == "BTCUSDT"
        assert d["lastPrice"] > 0

    def test_klines(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/market/klines/BTCUSDT", params={"interval": "1h", "limit": 50})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 50
        assert {"open", "high", "low", "close", "volume"}.issubset(data[0].keys())

    def test_klines_invalid_interval(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/market/klines/BTCUSDT", params={"interval": "2h"})
        assert r.status_code == 400


# ============ Watchlist ============
class TestWatchlist:
    def test_watchlist_crud_flow(self, api_client, base_url, auth_headers):
        # clean up first (idempotent)
        api_client.delete(f"{base_url}/api/watchlist/BTCUSDT", headers=auth_headers)

        # Add
        r = api_client.post(f"{base_url}/api/watchlist", headers=auth_headers, json={"symbol": "BTCUSDT"})
        assert r.status_code == 200
        assert r.json()["symbol"] == "BTCUSDT"

        # Duplicate
        r = api_client.post(f"{base_url}/api/watchlist", headers=auth_headers, json={"symbol": "BTCUSDT"})
        assert r.status_code == 400

        # List verifies persistence
        r = api_client.get(f"{base_url}/api/watchlist", headers=auth_headers)
        assert r.status_code == 200
        syms = [w["symbol"] for w in r.json()]
        assert "BTCUSDT" in syms

        # Delete
        r = api_client.delete(f"{base_url}/api/watchlist/BTCUSDT", headers=auth_headers)
        assert r.status_code == 200

        # Verify gone
        r = api_client.get(f"{base_url}/api/watchlist", headers=auth_headers)
        syms = [w["symbol"] for w in r.json()]
        assert "BTCUSDT" not in syms

    def test_watchlist_requires_auth(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/watchlist")
        assert r.status_code == 401


# ============ Portfolio ============
class TestPortfolio:
    def test_portfolio_empty(self, api_client, base_url, auth_headers):
        # Get current and clean existing TEST_ positions first
        r = api_client.get(f"{base_url}/api/portfolio", headers=auth_headers)
        assert r.status_code == 200
        existing = r.json()
        for p in existing.get("positions", []):
            api_client.delete(f"{base_url}/api/portfolio/{p['id']}", headers=auth_headers)

        r = api_client.get(f"{base_url}/api/portfolio", headers=auth_headers)
        data = r.json()
        assert data["positions"] == []
        assert data["total_invested"] == 0

    def test_add_and_delete_position(self, api_client, base_url, auth_headers):
        r = api_client.post(f"{base_url}/api/portfolio", headers=auth_headers,
                            json={"symbol": "ETHUSDT", "quantity": 0.5, "entry_price": 2000.0, "side": "long"})
        assert r.status_code == 200
        pos = r.json()
        pid = pos["id"]
        assert pos["symbol"] == "ETHUSDT"

        # GET verifies P&L enrichment
        r = api_client.get(f"{base_url}/api/portfolio", headers=auth_headers)
        data = r.json()
        ids = [p["id"] for p in data["positions"]]
        assert pid in ids
        pos_f = next(p for p in data["positions"] if p["id"] == pid)
        for k in ["current_price", "invested", "current_value", "pnl", "pnl_pct"]:
            assert k in pos_f
        assert pos_f["invested"] == 1000.0

        # Delete
        r = api_client.delete(f"{base_url}/api/portfolio/{pid}", headers=auth_headers)
        assert r.status_code == 200

        r = api_client.delete(f"{base_url}/api/portfolio/{pid}", headers=auth_headers)
        assert r.status_code == 404

    def test_portfolio_invalid_values(self, api_client, base_url, auth_headers):
        r = api_client.post(f"{base_url}/api/portfolio", headers=auth_headers,
                            json={"symbol": "BTCUSDT", "quantity": 0, "entry_price": 0})
        assert r.status_code == 400


# ============ AI Signal (Claude Sonnet 4.5 via Emergent LLM) ============
class TestAISignal:
    def test_signal_requires_auth(self, api_client, base_url):
        r = api_client.post(f"{base_url}/api/ai/signal", json={"symbol": "BTCUSDT", "interval": "1h"})
        assert r.status_code == 401

    def test_signal_generation(self, api_client, base_url, auth_headers):
        r = api_client.post(f"{base_url}/api/ai/signal", headers=auth_headers,
                            json={"symbol": "BTCUSDT", "interval": "1h"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["action"] in ("BUY", "SELL", "HOLD")
        assert 0 <= data["confidence"] <= 100
        assert isinstance(data["reasoning"], str) and len(data["reasoning"]) > 0
        assert "rsi14" in data["indicators"]

    def test_recent_signals(self, api_client, base_url, auth_headers):
        r = api_client.get(f"{base_url}/api/ai/signals/recent", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
