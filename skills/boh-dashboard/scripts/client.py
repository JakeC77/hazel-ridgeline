"""
Supabase REST client for boh-dashboard skill.
Shared by all scripts — import as: import sys, os; sys.path.insert(0, os.path.dirname(__file__)); import client as SB
"""
import os, requests

# Auto-load .env from workspace if env vars aren't set (e.g. inside sandbox)
def _load_dotenv():
    """Walk up from this script's directory to find and load a .env file."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        env_path = os.path.join(d, ".env")
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip('"'))
            return
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

if not os.getenv("BOH_SUPABASE_KEY") and not os.getenv("SUPABASE_SERVICE_KEY"):
    _load_dotenv()

SUPABASE_URL = os.getenv("BOH_SUPABASE_URL", "https://zrolyrtaaaiauigrvusl.supabase.co")
SUPABASE_KEY = os.getenv("BOH_SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def get(table, params=None):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def insert(table, payload):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def update(table, payload, match: dict):
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=payload, params=params)
    r.raise_for_status()
    return r.json()

def delete_rows(table, match: dict):
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()
