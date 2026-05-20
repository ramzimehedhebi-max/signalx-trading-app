"""
Backend test for new bot endpoints (presets, force-close) and daily summary infra.
"""
import sys
import requests

BASE_URL = "http://localhost:8001/api"
TEST_EMAIL = "trader@test.com"
TEST_PASS = "test1234"

results = []


def record(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} :: {detail}")
    results.append((name, ok, detail))


def login():
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASS}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Login failed {r.status_code}: {r.text}")
    return r.json()["token"]


def test_unauth():
    cases = [
        ("GET", "/bot/presets"),
        ("POST", "/bot/preset/balanced"),
        ("POST", "/bot/positions/fake-id-12345/force-close"),
    ]
    for method, path in cases:
        r = requests.request(method, f"{BASE_URL}{path}", timeout=10)
        ok = r.status_code in (401, 403)
        record(f"AUTH 401 on {method} {path}", ok, f"status={r.status_code} body={r.text[:120]}")


def test_presets(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/bot/presets", headers=h, timeout=10)
    ok = r.status_code == 200
    record("GET /bot/presets -> 200", ok, f"status={r.status_code}")
    if not ok:
        return
    data = r.json()
    presets = data.get("presets", [])
    record("3 presets returned", len(presets) == 3, f"count={len(presets)}")
    by_name = {p["name"]: p for p in presets}
    for name, expected_tp in [("conservative", 3.0), ("balanced", 5.0), ("aggressive", 5.0)]:
        cfg = by_name.get(name, {}).get("config", {})
        tp = cfg.get("take_profit_pct")
        record(
            f"preset {name} take_profit_pct={expected_tp}",
            tp == expected_tp,
            f"got={tp}",
        )


def test_apply_preset(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/bot/preset/balanced", headers=h, timeout=10)
    ok = r.status_code == 200
    record("POST /bot/preset/balanced -> 200", ok, f"status={r.status_code} body={r.text[:200]}")

    r = requests.get(f"{BASE_URL}/bot/config", headers=h, timeout=10)
    ok2 = r.status_code == 200
    record("GET /bot/config after preset -> 200", ok2, f"status={r.status_code}")
    if ok2:
        cfg = r.json()
        record(
            "Config take_profit_pct == 5.0 after balanced preset",
            cfg.get("take_profit_pct") == 5.0,
            f"got={cfg.get('take_profit_pct')}",
        )
        record(
            "Config max_positions == 5 after balanced preset",
            cfg.get("max_positions") == 5,
            f"got={cfg.get('max_positions')}",
        )


def test_invalid_preset(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/bot/preset/nonexistent", headers=h, timeout=10)
    ok = r.status_code == 404
    record("POST /bot/preset/nonexistent -> 404", ok, f"status={r.status_code} body={r.text[:200]}")


def test_force_close_fake(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/bot/positions/fake-id-12345/force-close", headers=h, timeout=10)
    ok = r.status_code == 404
    record(
        "POST /bot/positions/fake-id-12345/force-close -> 404",
        ok,
        f"status={r.status_code} body={r.text[:200]}",
    )


def test_force_close_real(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.put(f"{BASE_URL}/bot/config", headers=h, json={"enabled": True}, timeout=10)
    if r.status_code != 200:
        record("Enable bot (for force-close real test)", False, f"status={r.status_code} body={r.text[:200]}")
        return
    record("Enable bot", True, "")
    r = requests.post(f"{BASE_URL}/bot/run-now", headers=h, timeout=60)
    record("POST /bot/run-now", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

    r = requests.get(f"{BASE_URL}/bot/positions", headers=h, timeout=15)
    if r.status_code != 200:
        record("GET /bot/positions (for force-close target)", False, f"status={r.status_code}")
        return
    positions = r.json()
    if not positions:
        record(
            "Force-close real position (best-effort)",
            True,
            "SKIPPED: no position was created (no entry signal). Fake-id 404 already verified.",
        )
        return
    pos = positions[0]
    pos_id = pos["id"]
    symbol = pos["symbol"]
    r = requests.post(f"{BASE_URL}/bot/positions/{pos_id}/force-close", headers=h, timeout=20)
    ok = r.status_code == 200
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    record(
        f"POST /bot/positions/<id>/force-close on {symbol} -> 200",
        ok,
        f"status={r.status_code} body={r.text[:200]}",
    )
    if ok:
        record("Force-close response ok=true", body.get("ok") is True, f"body={body}")
        record("Force-close response has symbol", body.get("symbol") == symbol, f"got={body.get('symbol')}")
        record("Force-close response has exit_price", isinstance(body.get("exit_price"), (int, float)),
               f"got={body.get('exit_price')}")
        r = requests.get(f"{BASE_URL}/bot/positions", headers=h, timeout=10)
        if r.status_code == 200:
            still_open = [p for p in r.json() if p["id"] == pos_id]
            record("Position closed (not in open list)", len(still_open) == 0,
                   f"still_open={len(still_open)}")


def test_existing_endpoints(token):
    h = {"Authorization": f"Bearer {token}"}
    checks = [
        ("GET", "/bot/config", 200),
        ("GET", "/bot/stats", 200),
        ("GET", "/bot/positions", 200),
        ("GET", "/bot/trades", 200),
    ]
    for method, path, expected in checks:
        r = requests.request(method, f"{BASE_URL}{path}", headers=h, timeout=15)
        ok = r.status_code == expected
        record(f"{method} {path} -> {expected}", ok, f"status={r.status_code}")

    r = requests.put(f"{BASE_URL}/bot/config", headers=h, json={"interval_minutes": 5}, timeout=10)
    record("PUT /bot/config {interval_minutes:5} -> 200", r.status_code == 200, f"status={r.status_code}")


def main():
    print(f"BASE_URL={BASE_URL}")
    test_unauth()
    try:
        token = login()
        print(f"Got token (len={len(token)})")
        record("Login as trader@test.com", True, "")
    except Exception as e:
        record("Login", False, str(e))
        return
    test_presets(token)
    test_apply_preset(token)
    test_invalid_preset(token)
    test_force_close_fake(token)
    test_force_close_real(token)
    test_existing_endpoints(token)

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== RESULT {passed}/{total} PASSED ===")
    fails = [(n, d) for n, ok, d in results if not ok]
    if fails:
        print("\nFAILURES:")
        for n, d in fails:
            print(f"  - {n} :: {d}")
        sys.exit(1)


if __name__ == "__main__":
    main()
