"""
Comprehensive smoke test for SignalX backend.
Tests the 12 areas described in the latest review request.
"""
import sys
import time
import requests

BASE = "http://localhost:8001/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "Trader2026"

results = []


def record(area, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {area} :: {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append({"area": area, "name": name, "passed": passed, "detail": detail})


def login():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    if r.status_code != 200:
        print("Login failed:", r.status_code, r.text)
        sys.exit(1)
    return r.json()["token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    token = login()
    print(f"\n=== Logged in as {EMAIL} ===\n")

    # 1. AUTH
    r = requests.get(f"{BASE}/auth/me", headers=H(token), timeout=10)
    ok = r.status_code == 200 and r.json().get("email") == EMAIL
    record("1.Auth", "GET /auth/me with token", ok, f"status={r.status_code} body={r.text[:160]}")

    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": "WrongPassword!"}, timeout=10)
    record("1.Auth", "Login with wrong password → 401", r.status_code == 401, f"status={r.status_code}")

    # 2. PREMIUM LIFETIME
    r = requests.get(f"{BASE}/premium/status", headers=H(token), timeout=10)
    j = r.json() if r.status_code == 200 else {}
    ok = (
        r.status_code == 200
        and j.get("is_premium") is True
        and j.get("status") == "lifetime"
        and j.get("lifetime") is True
    )
    record("2.Premium", "GET /premium/status lifetime grant", ok, f"status={r.status_code} body={j}")

    # 3. FREE TIER LIMITS BYPASS
    ten_pairs = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT"]
    r = requests.put(f"{BASE}/bot/config", headers=H(token), json={"pairs": ten_pairs}, timeout=15)
    record("3.PremiumBypass", "PUT /bot/config with 10 pairs (lifetime)", r.status_code == 200,
           f"status={r.status_code} body={r.text[:200]}")

    p1 = requests.post(f"{BASE}/ai/predict", headers=H(token),
                       json={"symbol": "BTCUSDT", "horizon": "24h"}, timeout=60)
    p2 = requests.post(f"{BASE}/ai/predict", headers=H(token),
                       json={"symbol": "BTCUSDT", "horizon": "24h"}, timeout=60)
    ok = p1.status_code == 200 and p2.status_code == 200
    record("3.PremiumBypass", "POST /ai/predict twice (no rate-limit for lifetime)",
           ok, f"call1={p1.status_code} call2={p2.status_code}")

    # 4. FORGOT PASSWORD RATE-LIMIT
    r1 = requests.post(f"{BASE}/auth/forgot-password", json={"email": EMAIL}, timeout=10)
    r2 = requests.post(f"{BASE}/auth/forgot-password", json={"email": EMAIL}, timeout=10)
    ok2 = r2.status_code == 429 and ("Patiente" in r2.text)
    record("4.ForgotPwd", "2nd immediate forgot-password call → 429 with 'Patiente X secondes'", ok2,
           f"r1={r1.status_code} r2={r2.status_code} r2body={r2.text[:160]}")
    record("4.ForgotPwd", "1st forgot-password call (200 if cleared, 429 if rate-limited)",
           r1.status_code in (200, 429),
           f"r1.status={r1.status_code} r1.body={r1.text[:160]}")

    # 5. RESET PASSWORD with code 000000
    r = requests.post(f"{BASE}/auth/reset-password", json={
        "email": EMAIL, "code": "000000", "new_password": "Whatever2026X"
    }, timeout=10)
    ok = r.status_code == 400 and "Code invalide" in r.text
    record("5.ResetPwd", "POST /auth/reset-password with bad code → 400", ok,
           f"status={r.status_code} body={r.text[:160]}")

    # 6. BINANCE STATUS
    r = requests.get(f"{BASE}/binance/status", headers=H(token), timeout=10)
    j = r.json() if r.status_code == 200 else {}
    record("6.Binance", "GET /binance/status connected:false",
           r.status_code == 200 and j.get("connected") is False,
           f"status={r.status_code} body={j}")

    r = requests.get(f"{BASE}/binance/account", headers=H(token), timeout=10)
    ok = r.status_code == 400 and "Binance non connecté" in r.text
    record("6.Binance", "GET /binance/account → 400 not connected", ok,
           f"status={r.status_code} body={r.text[:160]}")

    # 7. BOT ENDPOINTS
    r = requests.get(f"{BASE}/bot/config", headers=H(token), timeout=10)
    cfg = r.json() if r.status_code == 200 else {}
    has_fields = all(k in cfg for k in ("live_mode", "live_max_position_usdt", "live_killswitch"))
    record("7.Bot", "GET /bot/config has new fields", r.status_code == 200 and has_fields,
           f"status={r.status_code} live_mode={cfg.get('live_mode')} cap={cfg.get('live_max_position_usdt')} ks={cfg.get('live_killswitch')}")

    r = requests.get(f"{BASE}/bot/stats", headers=H(token), timeout=10)
    record("7.Bot", "GET /bot/stats", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/bot/positions", headers=H(token), timeout=10)
    record("7.Bot", "GET /bot/positions returns list",
           r.status_code == 200 and isinstance(r.json(), list),
           f"status={r.status_code}")

    r = requests.get(f"{BASE}/bot/trades", headers=H(token), timeout=10)
    record("7.Bot", "GET /bot/trades returns list",
           r.status_code == 200 and isinstance(r.json(), list),
           f"status={r.status_code}")

    # 8. LIVE MODE WITHOUT BINANCE → 400 expected (Binance check fires first)
    r = requests.put(f"{BASE}/bot/config", headers=H(token), json={"live_mode": True}, timeout=10)
    ok = r.status_code == 400 and "Binance" in r.text
    record("8.LiveMode", "PUT live_mode=true w/o Binance → 400", ok,
           f"status={r.status_code} body={r.text[:200]}")

    # 9. AI PREDICTIONS ETHUSDT 3d
    t0 = time.time()
    r = requests.post(f"{BASE}/ai/predict", headers=H(token),
                      json={"symbol": "ETHUSDT", "horizon": "3d"}, timeout=60)
    elapsed = time.time() - t0
    j = r.json() if r.status_code == 200 else {}
    has_fields = all(k in j for k in ("confidence", "target_low", "target_median", "target_high", "reasoning"))
    ok = r.status_code == 200 and has_fields and elapsed < 30
    record("9.AI", "POST /ai/predict ETHUSDT 3d (<30s, has fields)", ok,
           f"status={r.status_code} elapsed={elapsed:.1f}s has_fields={has_fields}")

    # 10. MARKETS — actual routes use SINGULAR 'market' and klines uses path param
    r = requests.get(f"{BASE}/market/tickers?symbols=BTCUSDT,ETHUSDT", timeout=10)
    ok = r.status_code == 200 and isinstance(r.json(), list)
    record("10.Markets", "GET /market/tickers (singular)", ok,
           f"status={r.status_code} count={len(r.json()) if ok else '-'}")

    r_plural = requests.get(f"{BASE}/markets/tickers?symbols=BTCUSDT,ETHUSDT", timeout=10)
    record("10.Markets", "GET /markets/tickers (plural — as written in review)",
           r_plural.status_code == 200,
           f"status={r_plural.status_code} (actual route is /market/tickers, NOT /markets/tickers)")

    r = requests.get(f"{BASE}/market/klines/BTCUSDT?interval=1h&limit=10", timeout=10)
    ok = r.status_code == 200 and isinstance(r.json(), list)
    record("10.Markets", "GET /market/klines/BTCUSDT (path param)", ok,
           f"status={r.status_code}")

    r_q = requests.get(f"{BASE}/markets/klines?symbol=BTCUSDT&interval=1h&limit=10", timeout=10)
    record("10.Markets", "GET /markets/klines?symbol=... (as in review)",
           r_q.status_code == 200,
           f"status={r_q.status_code} (actual route: /market/klines/{{symbol}})")

    # 11. NOTIFICATIONS
    r = requests.get(f"{BASE}/notifications", headers=H(token), timeout=10)
    j = r.json() if r.status_code == 200 else {}
    has_items = isinstance(j.get("items"), list)
    record("11.Notif", "GET /notifications returns object with items list",
           r.status_code == 200 and has_items,
           f"status={r.status_code} items={len(j.get('items',[])) if has_items else '-'} unread={j.get('unread')}")

    r = requests.get(f"{BASE}/notifications/unread-count", headers=H(token), timeout=10)
    j = r.json() if r.status_code == 200 else {}
    ok = r.status_code == 200 and "unread" in j
    record("11.Notif", "GET /notifications/unread-count",
           ok, f"status={r.status_code} body={j} (NOTE: key is 'unread' not 'count')")

    # 12. STRIPE
    r = requests.get(f"{BASE}/premium/status", headers=H(token), timeout=10)
    j = r.json() if r.status_code == 200 else {}
    record("12.Stripe", "stripe_configured=true",
           j.get("stripe_configured") is True,
           f"stripe_configured={j.get('stripe_configured')}")

    r = requests.post(f"{BASE}/premium/checkout", headers=H(token),
                      json={"success_url": "signalx://premium/success",
                            "cancel_url": "signalx://premium/cancel"}, timeout=20)
    url = None
    if r.status_code == 200:
        try:
            url = r.json().get("url")
        except Exception:
            url = None
    ok = bool(r.status_code == 200 and url and url.startswith("https://checkout.stripe.com/c/pay/cs_"))
    record("12.Stripe", "POST /premium/checkout returns Stripe checkout URL",
           ok, f"status={r.status_code} url={(url or '')[:80]} body={r.text[:160]}")

    r = requests.post(f"{BASE}/stripe/webhook", data=b"", timeout=10)
    record("12.Stripe", "POST /stripe/webhook no body → 400 invalid signature",
           r.status_code == 400, f"status={r.status_code} body={r.text[:120]}")

    # SUMMARY
    print("\n\n===== SUMMARY =====")
    by_area = {}
    for x in results:
        by_area.setdefault(x["area"], []).append(x)
    for area, items in sorted(by_area.items()):
        passed = sum(1 for i in items if i["passed"])
        total = len(items)
        marker = "✅" if passed == total else "❌"
        print(f"  {marker} {area}: {passed}/{total}")
    fails = [x for x in results if not x["passed"]]
    print(f"\nTotal: {sum(1 for x in results if x['passed'])}/{len(results)} passed")
    if fails:
        print("\nFAILS:")
        for f in fails:
            print(f"  - {f['area']} :: {f['name']} :: {f['detail']}")

    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
