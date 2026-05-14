"""
Test the Binance connect endpoint focusing on:
1. Geo-block handling (503 with GEO_BLOCKED prefix)
2. Force-save feature (?force=true) bypass
3. Status reflects connected state after force-save
4. Disconnect clears all binance_* fields

Run: python3 /app/backend_test_binance_force.py
"""
import os
import sys
import secrets
import httpx
import asyncio
import json

BACKEND_URL = "https://binance-profit-2.preview.emergentagent.com/api"
EMAIL = "ramzimehedhebi@gmail.com"
PASSWORD = "Trader2026"

results = []

def log(name, ok, detail=""):
    icon = "✅" if ok else "❌"
    print(f"{icon} {name} :: {detail}")
    results.append({"name": name, "ok": ok, "detail": detail})


async def main():
    async with httpx.AsyncClient(timeout=30.0, base_url=BACKEND_URL) as client:
        # 1) Login
        r = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            log("Login", False, f"HTTP {r.status_code} body={r.text[:200]}")
            return
        token = r.json().get("access_token") or r.json().get("token")
        if not token:
            log("Login", False, f"No token in response: {r.json()}")
            return
        log("Login", True, f"got token len={len(token)}")
        headers = {"Authorization": f"Bearer {token}"}

        # Pre-cleanup: disconnect if previously connected
        r = await client.delete("/binance/disconnect", headers=headers)
        log("Pre-cleanup disconnect", r.status_code == 200, f"HTTP {r.status_code}")

        # ====================
        # SCENARIO 1: invalid (short) keys WITHOUT force
        # ====================
        r = await client.post(
            "/binance/connect",
            headers=headers,
            json={"api_key": "shortkey", "api_secret": "shortsecret"},
        )
        body = r.text
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 400 and "Clés invalides" in (j.get("detail") or "")
        log(
            "1) Invalid (short) keys WITHOUT force → 400 'Clés invalides'",
            ok,
            f"HTTP {r.status_code} detail={j.get('detail')}",
        )

        # ====================
        # SCENARIO 2: valid-format fake keys WITHOUT force → expect 503 GEO_BLOCKED
        # ====================
        fake_key = secrets.token_hex(32)    # 64 chars
        fake_secret = secrets.token_hex(32)  # 64 chars
        r = await client.post(
            "/binance/connect",
            headers=headers,
            json={"api_key": fake_key, "api_secret": fake_secret},
        )
        try:
            j = r.json()
        except Exception:
            j = {}
        detail = j.get("detail") or ""
        is_geo = (r.status_code == 503) and detail.startswith("GEO_BLOCKED|")
        log(
            "2) Valid-format fake keys WITHOUT force → 503 GEO_BLOCKED|...",
            is_geo,
            f"HTTP {r.status_code} detail={detail[:120]}",
        )

        # ====================
        # SCENARIO 3a: valid-format fake keys WITH force=true → 200 unverified
        # ====================
        r = await client.post(
            "/binance/connect?force=true",
            headers=headers,
            json={"api_key": fake_key, "api_secret": fake_secret},
        )
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = (
            r.status_code == 200
            and j.get("ok") is True
            and j.get("unverified") is True
            and j.get("account_type") == "UNVERIFIED"
        )
        log(
            "3a) Force-save with valid-format keys → 200 ok+unverified+UNVERIFIED",
            ok,
            f"HTTP {r.status_code} body={j}",
        )

        # ====================
        # SCENARIO 3b: GET /binance/status reflects connected=true after force
        # ====================
        r = await client.get("/binance/status", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = (
            r.status_code == 200
            and j.get("connected") is True
            and j.get("can_trade") is True
        )
        log(
            "3b) GET /binance/status after force-save → connected=true, can_trade=true",
            ok,
            f"HTTP {r.status_code} body={j}",
        )

        # ====================
        # SCENARIO 3c: DB has all expected fields (via /binance/status fields above + try /binance/account)
        # ====================
        # /binance/account will likely fail (geo + invalid keys) but we just confirm the user
        # IS treated as connected (i.e. the endpoint runs the client, not 400 "non connecté")
        r = await client.get("/binance/account", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        # Should NOT return "Binance non connecté"
        not_disconnected = not (
            r.status_code == 400 and "non connecté" in (j.get("detail") or "")
        )
        log(
            "3c) GET /binance/account after force-save → NOT 'Binance non connecté'",
            not_disconnected,
            f"HTTP {r.status_code} detail={(j.get('detail') or '')[:120]}",
        )

        # ====================
        # SCENARIO 4: force=true with short keys → still 400
        # ====================
        # First disconnect to start clean
        await client.delete("/binance/disconnect", headers=headers)

        r = await client.post(
            "/binance/connect?force=true",
            headers=headers,
            json={"api_key": "abc", "api_secret": "def"},
        )
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 400 and "Clés invalides" in (j.get("detail") or "")
        log(
            "4) Force-save with INVALID (short) keys → STILL 400 'Clés invalides'",
            ok,
            f"HTTP {r.status_code} detail={j.get('detail')}",
        )

        # Verify status is now disconnected (since previous disconnect, and short-key force was rejected)
        r = await client.get("/binance/status", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 200 and j.get("connected") is False
        log(
            "4b) GET /binance/status after rejected force → connected=false",
            ok,
            f"HTTP {r.status_code} body={j}",
        )

        # ====================
        # SCENARIO 5: Reconnect via force=true, then DELETE /binance/disconnect clears
        # ====================
        r = await client.post(
            "/binance/connect?force=true",
            headers=headers,
            json={"api_key": fake_key, "api_secret": fake_secret},
        )
        ok = r.status_code == 200
        log("5a) Re-force-save to test disconnect cleanup", ok, f"HTTP {r.status_code}")

        r = await client.delete("/binance/disconnect", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 200 and j.get("ok") is True
        log("5b) DELETE /binance/disconnect → 200 {ok:true}", ok, f"HTTP {r.status_code} body={j}")

        # Verify status cleared
        r = await client.get("/binance/status", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 200 and j.get("connected") is False
        log(
            "5c) GET /binance/status after disconnect → connected=false",
            ok,
            f"HTTP {r.status_code} body={j}",
        )

        # Verify /binance/account returns 'non connecté'
        r = await client.get("/binance/account", headers=headers)
        try:
            j = r.json()
        except Exception:
            j = {}
        ok = r.status_code == 400 and "non connecté" in (j.get("detail") or "")
        log(
            "5d) GET /binance/account after disconnect → 400 'Binance non connecté'",
            ok,
            f"HTTP {r.status_code} body={j}",
        )

        # ====================
        # SCENARIO 6: Verify DB fields directly via motor
        # ====================
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            mongo_url = "mongodb://localhost:27017"
            # Use the env var from backend/.env
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.strip().split("=", 1)[1].strip().strip('"')
                        break
            mc = AsyncIOMotorClient(mongo_url)
            # Try common db name
            db_name = None
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("DB_NAME="):
                        db_name = line.strip().split("=", 1)[1].strip().strip('"')
                        break
            if db_name is None:
                # default fallback
                db_name = "test_database"
            mdb = mc[db_name]

            # Re-force connect
            r = await client.post(
                "/binance/connect?force=true",
                headers=headers,
                json={"api_key": fake_key, "api_secret": fake_secret},
            )
            assert r.status_code == 200

            u = await mdb.users.find_one({"email": EMAIL})
            checks = {
                "binance_api_key_enc": bool(u and u.get("binance_api_key_enc")),
                "binance_api_secret_enc": bool(u and u.get("binance_api_secret_enc")),
                "binance_connected_at": bool(u and u.get("binance_connected_at")),
                "binance_can_trade==True": (u and u.get("binance_can_trade") is True),
                "binance_unverified==True": (u and u.get("binance_unverified") is True),
            }
            ok = all(checks.values())
            log(
                "6) DB fields after force-save",
                ok,
                f"db={db_name} fields={checks}",
            )

            # Final cleanup: disconnect
            await client.delete("/binance/disconnect", headers=headers)
        except Exception as e:
            log("6) DB fields check", False, f"motor inspection failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    for r in results:
        if not r["ok"]:
            print(f"  ❌ {r['name']} — {r['detail']}")
    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
