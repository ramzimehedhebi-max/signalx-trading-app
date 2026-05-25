"""
Test the P&L baseline fix on the SignalX trading bot backend.

Tests:
 1. POST /api/auth/login → JWT
 2. GET /api/bot/stats → response contains capital_baseline + total_pnl_pct
 3. GET /api/bot/analytics → capital_start > 0, total_pnl_pct sane
 4. Regression: /api/bot/config, /api/bot/positions, /api/bot/trades, /api/bot/presets, /api/health
"""
import json
import math
import sys
import time
import uuid
import httpx

BASE = "http://127.0.0.1:8001/api"

CREDS = [
    ("ramzimehedhebi@gmail.com", "SignalX2026!"),
    ("trader@test.com", "test1234"),
]

results = []


def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} :: {detail}")
    results.append((name, ok, detail))


def login():
    """Try documented credentials, else register a new user."""
    with httpx.Client(base_url=BASE, timeout=20) as c:
        for email, pwd in CREDS:
            r = c.post("/auth/login", json={"email": email, "password": pwd})
            if r.status_code == 200 and r.json().get("token"):
                log("auth/login", True, f"using {email} (status=200, token len={len(r.json()['token'])})")
                return r.json()["token"], email
            else:
                print(f"  login attempt {email} → {r.status_code} {r.text[:120]}")

        # Register new user
        email = f"pnl_test_{uuid.uuid4().hex[:8]}@signalx.test"
        pwd = "Test1234!Sx"
        r = c.post("/auth/register", json={"email": email, "password": pwd, "name": "PnL Tester"})
        if r.status_code in (200, 201) and (r.json().get("token") or r.json().get("access_token")):
            tok = r.json().get("token") or r.json().get("access_token")
            log("auth/register (fallback)", True, f"new user {email}")
            return tok, email
        log("auth/login", False, f"all creds failed; register returned {r.status_code} {r.text[:200]}")
        sys.exit(1)


def main():
    token, email = login()
    H = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=BASE, timeout=30, headers=H) as c:
        # --- /api/health (no auth needed) ---
        rh = httpx.get(f"{BASE}/health", timeout=10)
        ok = rh.status_code == 200 and rh.json().get("ok") is True
        log("GET /health", ok, f"{rh.status_code} {rh.text[:120]}")

        # --- /api/bot/config (to know capital_usdt & live_mode) ---
        rcfg = c.get("/bot/config")
        ok = rcfg.status_code == 200
        cfg = rcfg.json() if ok else {}
        live_mode = bool(cfg.get("live_mode"))
        capital_usdt_cfg = float(cfg.get("capital_usdt", 0))
        log("GET /bot/config", ok, f"status={rcfg.status_code} live_mode={live_mode} capital_usdt={capital_usdt_cfg}")

        # --- /api/bot/stats ---
        rstats = c.get("/bot/stats")
        ok = rstats.status_code == 200
        log("GET /bot/stats status 200", ok, f"status={rstats.status_code}")
        stats = rstats.json() if ok else {}

        has_baseline = "capital_baseline" in stats
        has_pct = "total_pnl_pct" in stats
        log("GET /bot/stats has capital_baseline", has_baseline, f"present={has_baseline} value={stats.get('capital_baseline')}")
        log("GET /bot/stats has total_pnl_pct", has_pct, f"present={has_pct} value={stats.get('total_pnl_pct')}")

        cb = stats.get("capital_baseline")
        is_num = isinstance(cb, (int, float)) and math.isfinite(cb)
        log("capital_baseline is finite number", is_num, f"type={type(cb).__name__} value={cb}")

        pct = stats.get("total_pnl_pct")
        is_num2 = isinstance(pct, (int, float)) and math.isfinite(pct)
        log("total_pnl_pct is finite (not NaN/Inf)", is_num2, f"type={type(pct).__name__} value={pct}")

        # Paper mode: capital_baseline should equal cfg.capital_usdt
        if not live_mode:
            ok = abs(float(cb or 0) - capital_usdt_cfg) < 0.01
            log("paper mode: capital_baseline == cfg.capital_usdt", ok,
                f"baseline={cb} cfg.capital_usdt={capital_usdt_cfg}")
        else:
            log("paper mode: capital_baseline == cfg.capital_usdt", True,
                f"SKIP (user is LIVE mode, baseline={cb})")

        # --- /api/bot/analytics ---
        ranal = c.get("/bot/analytics")
        ok = ranal.status_code == 200
        log("GET /bot/analytics status 200", ok, f"status={ranal.status_code}")
        anal = ranal.json() if ok else {}

        cs = anal.get("capital_start")
        ok = isinstance(cs, (int, float)) and cs > 0
        log("analytics.capital_start > 0", ok, f"capital_start={cs}")

        tpp = anal.get("total_pnl_pct")
        ok = isinstance(tpp, (int, float)) and math.isfinite(tpp) and abs(tpp) < 1000
        log("analytics.total_pnl_pct reasonable (not extreme, finite)", ok, f"total_pnl_pct={tpp}")

        # Paper mode: capital_start should == cfg.capital_usdt
        if not live_mode:
            ok = abs(float(cs or 0) - capital_usdt_cfg) < 0.01
            log("paper mode: analytics.capital_start == cfg.capital_usdt", ok,
                f"capital_start={cs} cfg.capital_usdt={capital_usdt_cfg}")
        else:
            log("paper mode: analytics.capital_start == cfg.capital_usdt", True,
                f"SKIP (user is LIVE, capital_start={cs})")

        # capital_current = capital_start + realized + unrealized (within rounding)
        cc = anal.get("capital_current")
        rp = anal.get("realized_pnl", 0)
        up = anal.get("unrealized_pnl", 0)
        if isinstance(cc, (int, float)) and isinstance(cs, (int, float)):
            expected = cs + rp + up
            diff = abs(cc - expected)
            ok = diff < 0.05  # rounding tolerance
            log("analytics: capital_current = capital_start + realized + unrealized", ok,
                f"capital_current={cc} expected={round(expected, 2)} diff={round(diff, 4)}")
        else:
            log("analytics: capital_current = capital_start + realized + unrealized", False,
                f"capital_current={cc} capital_start={cs}")

        # --- Regression: /api/bot/positions ---
        rp_ = c.get("/bot/positions")
        ok = rp_.status_code == 200 and isinstance(rp_.json(), list)
        log("GET /bot/positions (200 + array)", ok, f"status={rp_.status_code} type={type(rp_.json()).__name__}")

        # --- Regression: /api/bot/trades ---
        rt_ = c.get("/bot/trades")
        ok = rt_.status_code == 200 and isinstance(rt_.json(), list)
        log("GET /bot/trades (200 + array)", ok, f"status={rt_.status_code} type={type(rt_.json()).__name__}")

        # --- Regression: /api/bot/presets (3 presets) ---
        rpr = c.get("/bot/presets")
        ok = rpr.status_code == 200
        body = rpr.json() if ok else {}
        presets = body.get("presets", [])
        ok2 = ok and len(presets) == 3
        log("GET /bot/presets (200, 3 presets)", ok2,
            f"status={rpr.status_code} count={len(presets)} names={[p.get('name') for p in presets]}")

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    for n, ok, d in results:
        if not ok:
            print(f"  FAIL: {n} :: {d}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
