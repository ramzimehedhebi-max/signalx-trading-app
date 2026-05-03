import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get("EXPO_PUBLIC_BACKEND_URL") else None
if not BASE_URL:
    # fallback: read frontend/.env
    from dotenv import dotenv_values
    fe = dotenv_values("/app/frontend/.env")
    BASE_URL = fe["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_token(api_client):
    # Login with known user; if fails, register it.
    creds = {"email": "trader@test.com", "password": "test1234"}
    r = api_client.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        api_client.post(f"{BASE_URL}/api/auth/register", json={**creds, "name": "Trader"})
        r = api_client.post(f"{BASE_URL}/api/auth/login", json=creds)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
