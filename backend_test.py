"""
Backend tests for Binance Live trading endpoints + BotConfig live fields.
"""
import os
import sys
import json
import requests

BASE = "http://localhost:8001/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "Trader2026"

results = []


def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name} :: {detail}"
    print(line)
    results.append((name, ok, detail))


def login():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    if r.status_code != 200:
        # Try to register first
        r2 = requests.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Ramzi"}, timeout=10)
        if r2.status_code != 200:
            print(f"Login failed {r.status_code} {r.text}; Register failed {r2.status_code} {r2.text}")
            sys.exit(1)
        return r2.json()["token"]
    return r.json()["token"]


def main():
    token = login()
    H = {"Authorization": f"Bearer {token}"}
    print(f"Auth OK, token len={len(token)}")

    # Ensure clean state: disconnect first if any
    r = requests.delete(f"{BASE}/binance/disconnect", headers=H, timeout=10)
    print(f"Pre-clean disconnect: {r.status_code} {r.text[:150]}")

    # 1) GET /api/binance/status (no keys connected yet)
    r = requests.get(f"{BASE}/binance/status", headers=H, timeout=10)
    ok = r.status_code == 200 and r.json().get("connected") is False
    log("1. GET /binance/status (not connected)", ok, f"{r.status_code} {r.text}")

    # 2) POST /api/binance/connect with INVALID (len>=20) keys → should 400
    body = {
        "api_key": "fake_invalid_key_with_more_than_20_chars_here",
        "api_secret": "fake_invalid_secret_with_more_than_20_chars_here",
    }
    r = requests.post(f"{BASE}/binance/connect", json=body, headers=H, timeout=15)
    ok = r.status_code == 400
    log("2. POST /binance/connect with INVALID keys", ok, f"{r.status_code} {r.text[:200]}")

    # 3) POST /api/binance/connect with TOO SHORT keys → 400 "Clés invalides"
    r = requests.post(f"{BASE}/binance/connect", json={"api_key": "short", "api_secret": "short"}, headers=H, timeout=10)
    body_text = r.text
    ok = r.status_code == 400 and "invalides" in body_text.lower()
    log("3. POST /binance/connect with SHORT keys", ok, f"{r.status_code} {body_text[:200]}")

    # 4) DELETE /api/binance/disconnect (idempotent)
    r = requests.delete(f"{BASE}/binance/disconnect", headers=H, timeout=10)
    ok = r.status_code == 200 and r.json().get("ok") is True
    log("4. DELETE /binance/disconnect (idempotent)", ok, f"{r.status_code} {r.text}")

    # 5) PUT /api/bot/config live_mode=true while NOT connected → 400 French msg
    r = requests.put(f"{BASE}/bot/config", json={"live_mode": True}, headers=H, timeout=10)
    body_text = r.text
    ok = r.status_code == 400 and "Connecte" in body_text and "Binance" in body_text
    log("5. PUT /bot/config live_mode=true (no keys)", ok, f"{r.status_code} {body_text[:200]}")

    # 6) PUT /api/bot/config live_mode=false → 200
    r = requests.put(f"{BASE}/bot/config", json={"live_mode": False}, headers=H, timeout=10)
    ok = r.status_code == 200 and r.json().get("live_mode") is False
    log("6. PUT /bot/config live_mode=false", ok, f"{r.status_code} live_mode={r.json().get('live_mode') if r.status_code==200 else 'N/A'}")

    # 7) PUT /api/bot/config live_max_position_usdt=25 + live_killswitch=false
    r = requests.put(
        f"{BASE}/bot/config",
        json={"live_max_position_usdt": 25, "live_killswitch": False},
        headers=H,
        timeout=10,
    )
    if r.status_code == 200:
        cfg = r.json()
        ok = (cfg.get("live_max_position_usdt") == 25 and cfg.get("live_killswitch") is False)
        detail = f"cap={cfg.get('live_max_position_usdt')} killswitch={cfg.get('live_killswitch')}"
    else:
        ok = False
        detail = f"{r.status_code} {r.text[:200]}"
    log("7. PUT /bot/config live_max_position_usdt=25 + live_killswitch=false", ok, detail)

    # 8) GET /api/bot/config has new fields
    r = requests.get(f"{BASE}/bot/config", headers=H, timeout=10)
    if r.status_code == 200:
        cfg = r.json()
        ok = all(k in cfg for k in ("live_mode", "live_max_position_usdt", "live_killswitch"))
        detail = f"live_mode={cfg.get('live_mode')} cap={cfg.get('live_max_position_usdt')} ks={cfg.get('live_killswitch')}"
    else:
        ok = False
        detail = f"{r.status_code} {r.text[:200]}"
    log("8. GET /bot/config has new live_* fields", ok, detail)

    # 9) GET /api/binance/account when NOT connected → 400
    r = requests.get(f"{BASE}/binance/account", headers=H, timeout=10)
    body_text = r.text
    ok = r.status_code == 400 and "non connecté" in body_text.lower()
    log("9. GET /binance/account (not connected)", ok, f"{r.status_code} {body_text[:200]}")

    # 10) GET /api/notifications/unread-count
    r = requests.get(f"{BASE}/notifications/unread-count", headers=H, timeout=10)
    ok = r.status_code == 200 and "unread" in r.json()
    log("10. GET /notifications/unread-count", ok, f"{r.status_code} {r.text[:200]}")

    print("\n========== SUMMARY ==========")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for name, ok, detail in results:
        print(f"{'✅' if ok else '❌'} {name}")
    print(f"\nTotal: {passed}/{len(results)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
