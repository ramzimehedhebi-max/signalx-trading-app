"""
Backend test for FREE TIER ENFORCEMENT (free-tier gates on /api/bot/config and /api/ai/predict).
Tests against http://localhost:8001/api with credentials ramzimehedhebi@gmail.com / Trader2026.
"""
import asyncio
import json
import os
import sys
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

BASE = "http://localhost:8001/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "Trader2026"

results = []


def log(name, ok, detail=""):
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name} :: {detail}")
    results.append({"name": name, "ok": ok, "detail": detail})


async def cleanup_quota(user_id):
    """Clean prediction_quota collection for this user, so test is deterministic."""
    mongo_url = "mongodb://localhost:27017"
    db_name = "test_database"
    cli = AsyncIOMotorClient(mongo_url)
    db = cli[db_name]
    res = await db.prediction_quota.delete_many({"user_id": user_id})
    cli.close()
    return res.deleted_count


async def main():
    async with httpx.AsyncClient(timeout=60.0) as http:
        # 1. Login
        r = await http.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            log("Login", False, f"status={r.status_code} body={r.text[:200]}")
            return
        token = r.json()["token"]
        user_id = r.json()["user"]["id"]
        log("Login", True, f"user_id={user_id}")
        headers = {"Authorization": f"Bearer {token}"}

        # Sanity: premium status
        r = await http.get(f"{BASE}/premium/status", headers=headers)
        ok = r.status_code == 200 and r.json().get("is_premium") is False
        log("GET /premium/status (is_premium=false)", ok, f"status={r.status_code} body={r.text[:200]}")

        # Save current pairs to restore later
        r = await http.get(f"{BASE}/bot/config", headers=headers)
        original_pairs = r.json().get("pairs", [])

        # =========== TEST 1: 5 pairs (exceeds Free limit of 3) ===========
        body = {"pairs": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]}
        r = await http.put(f"{BASE}/bot/config", headers=headers, json=body)
        ok = r.status_code == 402 and "Plan Free limité à 3 paires" in r.text
        log("PUT /bot/config 5 pairs → 402", ok,
            f"status={r.status_code} body={r.text[:300]}")

        # =========== TEST 2: 3 pairs (within Free limit) ===========
        body = {"pairs": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]}
        r = await http.put(f"{BASE}/bot/config", headers=headers, json=body)
        ok = r.status_code == 200
        if ok:
            cfg = r.json()
            ok = cfg.get("pairs") == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        log("PUT /bot/config 3 pairs → 200", ok,
            f"status={r.status_code} pairs={r.json().get('pairs') if r.status_code == 200 else r.text[:200]}")

        # =========== TEST 3: live_mode=true (Premium-only) ===========
        body = {"live_mode": True}
        r = await http.put(f"{BASE}/bot/config", headers=headers, json=body)
        # Either 400 (Binance not connected) OR 402 (Premium gate). NOT 500.
        is_400_binance = r.status_code == 400 and "Binance" in r.text
        is_402_premium = r.status_code == 402 and ("Premium" in r.text or "premium" in r.text)
        ok = is_400_binance or is_402_premium
        log("PUT /bot/config live_mode=true → 400 or 402 (not 500)", ok,
            f"status={r.status_code} body={r.text[:300]}")

        # =========== TEST 4 & 5: AI predict quota enforcement ===========
        # Cleanup quota first
        try:
            n = await cleanup_quota(user_id)
            print(f"  [cleanup] removed {n} prediction_quota entries")
        except Exception as e:
            print(f"  [cleanup] failed: {e}")

        # First call should succeed
        body = {"symbol": "BTCUSDT", "horizon": "24h"}
        r1 = await http.post(f"{BASE}/ai/predict", headers=headers, json=body)
        first_ok = r1.status_code == 200
        log("POST /ai/predict (1st call) → 200", first_ok,
            f"status={r1.status_code} body={r1.text[:200]}")

        # Second call should be 402
        r2 = await http.post(f"{BASE}/ai/predict", headers=headers, json=body)
        second_ok = r2.status_code == 402 and "1 prédiction(s) IA par jour" in r2.text
        log("POST /ai/predict (2nd call) → 402 quota", second_ok,
            f"status={r2.status_code} body={r2.text[:300]}")

        # =========== TEST 6: Sanity checks ===========
        r = await http.get(f"{BASE}/bot/config", headers=headers)
        ok = r.status_code == 200
        log("GET /bot/config → 200", ok, f"status={r.status_code}")

        r = await http.get(f"{BASE}/premium/status", headers=headers)
        ok = r.status_code == 200 and r.json().get("is_premium") is False
        log("GET /premium/status → 200 is_premium=false", ok,
            f"status={r.status_code} body={r.text[:200]}")

        # Restore pairs (best effort - cap at 3 since Free user)
        await http.put(f"{BASE}/bot/config", headers=headers,
                       json={"pairs": original_pairs[:3] if len(original_pairs) > 3 else original_pairs})

    # Summary
    print("\n=== SUMMARY ===")
    pass_count = sum(1 for r in results if r["ok"])
    print(f"Passed: {pass_count}/{len(results)}")
    for r in results:
        sym = "PASS" if r["ok"] else "FAIL"
        print(f"  [{sym}] {r['name']}")
    sys.exit(0 if pass_count == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
