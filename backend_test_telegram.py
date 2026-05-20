"""
Backend test for Telegram notification endpoints + regression on existing
notification endpoints.

Endpoints under test:
  - GET  /api/notifications/telegram/status (auth required)
  - POST /api/notifications/telegram/test   (auth required)
  - GET  /api/notifications                 (regression)
  - GET  /api/notifications/unread-count    (regression)
  - POST /api/notifications/read-all        (regression)
"""
import os
import sys
import json
import requests

BASE = "http://127.0.0.1:8001/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "SignalX2026!"
FALLBACK_EMAIL = "trader@test.com"
FALLBACK_PASSWORD = "test1234"

results = []  # (name, passed, detail)


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    flag = "PASS" if passed else "FAIL"
    print(f"[{flag}] {name} :: {detail}")


def login():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    if r.status_code != 200:
        print(f"[warn] admin login failed ({r.status_code}); falling back to test account")
        r = requests.post(f"{BASE}/auth/login", json={"email": FALLBACK_EMAIL, "password": FALLBACK_PASSWORD}, timeout=15)
        if r.status_code != 200:
            raise SystemExit(f"Login failed: {r.status_code} {r.text}")
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    if not tok:
        raise SystemExit(f"No token in login response: {r.text}")
    return tok


def main():
    # 1. Auth required: GET /telegram/status without token → 401
    r = requests.get(f"{BASE}/notifications/telegram/status", timeout=10)
    record(
        "GET /notifications/telegram/status without auth → 401",
        r.status_code == 401,
        f"status={r.status_code} body={r.text[:120]}",
    )

    # 2. Auth required: POST /telegram/test without token → 401
    r = requests.post(f"{BASE}/notifications/telegram/test", timeout=10)
    record(
        "POST /notifications/telegram/test without auth → 401",
        r.status_code == 401,
        f"status={r.status_code} body={r.text[:120]}",
    )

    token = login()
    H = {"Authorization": f"Bearer {token}"}
    print(f"[info] logged in as {EMAIL}")

    # 3. GET /telegram/status with auth → 200 with 3 booleans
    r = requests.get(f"{BASE}/notifications/telegram/status", headers=H, timeout=10)
    ok = False
    detail = f"status={r.status_code} body={r.text[:200]}"
    if r.status_code == 200:
        try:
            j = r.json()
            ok = (
                "configured" in j
                and "token_set" in j
                and "chat_id_set" in j
                and isinstance(j["configured"], bool)
                and isinstance(j["token_set"], bool)
                and isinstance(j["chat_id_set"], bool)
            )
            detail = f"status=200 json={j}"
        except Exception as e:
            detail = f"json parse error: {e} body={r.text[:200]}"
    record("GET /telegram/status returns 3 booleans", ok, detail)

    # Save state for later assertions
    try:
        status_json = r.json() if r.status_code == 200 else {}
    except Exception:
        status_json = {}

    # 4. In this dev env, TELEGRAM env vars are NOT set → all false
    if status_json:
        record(
            "telegram/status reports configured=false (dev env)",
            status_json.get("configured") is False
            and status_json.get("token_set") is False
            and status_json.get("chat_id_set") is False,
            f"json={status_json}",
        )

    # 5. POST /telegram/test without env vars → 400 with French detail
    r = requests.post(f"{BASE}/notifications/telegram/test", headers=H, timeout=10)
    ok = r.status_code == 400
    detail = f"status={r.status_code} body={r.text[:300]}"
    msg_ok = False
    try:
        j = r.json()
        msg = j.get("detail", "")
        msg_ok = "Telegram non configuré" in msg
    except Exception:
        msg = ""
    record(
        "POST /telegram/test (no env) → 400",
        ok,
        detail,
    )
    record(
        "POST /telegram/test (no env) → French 'Telegram non configuré' detail",
        msg_ok,
        f"detail={msg!r}",
    )

    # 6. Regression: GET /notifications
    r = requests.get(f"{BASE}/notifications", headers=H, timeout=10)
    ok = False
    detail = f"status={r.status_code}"
    if r.status_code == 200:
        try:
            j = r.json()
            ok = isinstance(j, dict) and "items" in j and "unread" in j
            detail = f"status=200 items_len={len(j.get('items', []))} unread={j.get('unread')}"
        except Exception as e:
            detail = f"parse error: {e}"
    record("GET /notifications → 200 with items+unread", ok, detail)

    # 7. Regression: GET /notifications/unread-count
    r = requests.get(f"{BASE}/notifications/unread-count", headers=H, timeout=10)
    ok = False
    detail = f"status={r.status_code} body={r.text[:160]}"
    if r.status_code == 200:
        try:
            j = r.json()
            ok = "unread" in j and isinstance(j["unread"], int)
            detail = f"status=200 unread={j.get('unread')}"
        except Exception as e:
            detail = f"parse error: {e}"
    record("GET /notifications/unread-count → 200 {unread:int}", ok, detail)

    # 8. Regression: POST /notifications/read-all
    r = requests.post(f"{BASE}/notifications/read-all", headers=H, timeout=10)
    ok = False
    detail = f"status={r.status_code} body={r.text[:160]}"
    if r.status_code == 200:
        try:
            j = r.json()
            ok = j.get("ok") is True
            detail = f"status=200 json={j}"
        except Exception as e:
            detail = f"parse error: {e}"
    record("POST /notifications/read-all → 200 {ok:true}", ok, detail)

    # Confirm unread is now 0
    r = requests.get(f"{BASE}/notifications/unread-count", headers=H, timeout=10)
    try:
        unread_after = r.json().get("unread")
    except Exception:
        unread_after = None
    record(
        "Unread count is 0 after read-all",
        unread_after == 0,
        f"unread_after={unread_after}",
    )

    # Summary
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"\n=== SUMMARY: {passed}/{total} passed ===")
    for name, p, detail in results:
        if not p:
            print(f"  FAIL: {name} :: {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
