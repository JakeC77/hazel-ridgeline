"""
Supabase REST client for boh-dashboard skill.
Shared by all scripts — import as: import sys, os; sys.path.insert(0, os.path.dirname(__file__)); import client as SB
"""
import os, requests

SUPABASE_URL = os.getenv("BOH_SUPABASE_URL", "https://zrolyrtaaaiauigrvusl.supabase.co")
SUPABASE_KEY = os.getenv("BOH_SUPABASE_KEY", "sb_secret_2SaPLNtI9TvqKVrgSaYRSg_bmfgl1a3")

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
