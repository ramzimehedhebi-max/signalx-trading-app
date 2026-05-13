"""
Backend tests for the new Stripe Premium subscription endpoints.
Stripe is intentionally NOT configured (placeholder env vars).
We verify the short-circuits and signature failures behave correctly.
"""
import sys
import requests

BASE = "http://localhost:8001/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "Trader2026"

results = []


def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} :: {detail}")
    results.append((name, ok, detail))


def login():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    if r.status_code != 200:
        r2 = requests.post(
            f"{BASE}/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "name": "Ramzi"},
            timeout=10,
        )
        if r2.status_code != 200:
            print(f"Login failed {r.status_code} {r.text}; Register failed {r2.status_code} {r2.text}")
            sys.exit(1)
        return r2.json()["token"]
    return r.json()["token"]


def main():
    token = login()
    H = {"Authorization": f"Bearer {token}"}
    print(f"Auth OK, token len={len(token)}")

    # 1) GET /api/premium/status (not premium, stripe not configured)
    r = requests.get(f"{BASE}/premium/status", headers=H, timeout=10)
    if r.status_code == 200:
        j = r.json()
        ok = (
            j.get("is_premium") is False
            and j.get("status") in (None, "",)
            and j.get("stripe_configured") is False
        )
        detail = f"is_premium={j.get('is_premium')} status={j.get('status')!r} stripe_configured={j.get('stripe_configured')}"
    else:
        ok = False
        detail = f"{r.status_code} {r.text[:200]}"
    log("1. GET /premium/status (not premium, stripe not configured)", ok, detail)

    # 2) POST /api/premium/checkout (Stripe NOT configured) → 503 with French message
    r = requests.post(f"{BASE}/premium/checkout", headers=H, timeout=10)
    body = r.text
    ok = r.status_code == 503 and (
        "Paiements indisponibles" in body or "Stripe n'est pas encore configur" in body
    )
    log("2. POST /premium/checkout (stripe not configured)", ok, f"{r.status_code} {body[:250]}")

    # 3) POST /api/premium/cancel (no active sub) → 503 (not configured) OR 400 (no sub). NOT 500.
    r = requests.post(f"{BASE}/premium/cancel", headers=H, timeout=10)
    ok = r.status_code in (400, 503) and r.status_code != 500
    log("3. POST /premium/cancel (no active sub, stripe not configured)", ok, f"{r.status_code} {r.text[:200]}")

    # 4) POST /api/stripe/webhook (no signature header) → 400 "Invalid signature"
    r = requests.post(
        f"{BASE}/stripe/webhook",
        data=b'{"id":"evt_test","type":"customer.subscription.created"}',
        headers={"Content-Type": "application/json"},  # NO stripe-signature header
        timeout=10,
    )
    body = r.text
    ok = r.status_code == 400 and "Invalid signature" in body
    log("4. POST /stripe/webhook (no signature header)", ok, f"{r.status_code} {body[:200]}")

    # 5) Sanity: existing endpoints still work
    r = requests.get(f"{BASE}/auth/me", headers=H, timeout=10)
    ok = r.status_code == 200 and "email" in r.json()
    log("5a. GET /auth/me (sanity)", ok, f"{r.status_code} {r.text[:120]}")

    r = requests.get(f"{BASE}/binance/status", headers=H, timeout=10)
    ok = r.status_code == 200 and r.json().get("connected") is False
    log("5b. GET /binance/status (sanity, not connected)", ok, f"{r.status_code} {r.text[:120]}")

    r = requests.get(f"{BASE}/bot/config", headers=H, timeout=10)
    ok = r.status_code == 200 and "live_mode" in r.json()
    log("5c. GET /bot/config (sanity)", ok, f"{r.status_code} keys={list(r.json().keys())[:8] if r.status_code==200 else 'N/A'}")

    print("\n========== SUMMARY ==========")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    print(f"\nTotal: {passed}/{len(results)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
