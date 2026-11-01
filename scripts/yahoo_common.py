"""Yahoo Fantasy: token storage + API helpers (used by yahoo_connect.py and update_yahoo.py).

The OAuth refresh token is stored encrypted in data/private/yahoo_token.enc (AES-256 via openssl,
passphrase = the YAHOO_CLIENT_SECRET repo secret), so the repo can be public and the token still
can't be read. Yahoo may hand back a new refresh token on each refresh; we always save the latest.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "data" / "private" / "yahoo_token.enc"
AUTH = "https://api.login.yahoo.com/oauth2/get_token"
API = "https://fantasysports.yahooapis.com/fantasy/v2"


def creds() -> tuple[str, str]:
    cid, sec = os.environ.get("YAHOO_CLIENT_ID", "").strip(), os.environ.get("YAHOO_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        raise SystemExit("YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET repo secrets are missing")
    return cid, sec


def _openssl(args: list[str], data: bytes) -> bytes:
    _, sec = creds()
    env = {**os.environ, "YK": sec}
    return subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt", "-pass", "env:YK", *args],
                          input=data, capture_output=True, check=True, env=env).stdout


def save_token(tok: dict) -> None:
    keep = {"refresh_token": tok["refresh_token"], "xoauth_yahoo_guid": tok.get("xoauth_yahoo_guid")}
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_bytes(_openssl(["-a"], json.dumps(keep).encode()))


def load_token() -> dict:
    if not TOKEN_FILE.exists():
        raise SystemExit("No Yahoo token yet: run the 'Connect Yahoo league' workflow with the code from Yahoo")
    return json.loads(_openssl(["-d", "-a"], TOKEN_FILE.read_bytes()))


def token_request(data: dict) -> dict:
    cid, sec = creds()
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(AUTH, data={**data, "redirect_uri": "oob"}, headers={"Authorization": "Basic " + basic,
                      "Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    if r.status_code != 200:
        # never print the token; Yahoo's error text is safe to show
        try:
            err = r.json()
        except Exception:  # noqa: BLE001
            err = {"error": r.text[:200]}
        raise SystemExit(f"Yahoo token request failed ({r.status_code}): {err.get('error')} {err.get('error_description', '')}")
    return r.json()


def access_token() -> str:
    old = load_token()
    tok = token_request({"grant_type": "refresh_token", "refresh_token": old["refresh_token"]})
    if tok.get("refresh_token") and tok["refresh_token"] != old["refresh_token"]:
        save_token(tok)
    return tok["access_token"]


def api(path: str, token: str) -> dict:
    r = requests.get(f"{API}/{path}", params={"format": "json"}, headers={"Authorization": "Bearer " + token}, timeout=60)
    r.raise_for_status()
    return r.json()["fantasy_content"]


# Yahoo's JSON: objects come as lists of one-key dicts, collections as {"0": {...}, "1": {...}, "count": n}
def merge(x) -> dict:
    out: dict = {}
    if isinstance(x, dict):
        return x
    for item in x or []:
        if isinstance(item, list):
            out.update(merge(item))
        elif isinstance(item, dict):
            out.update(item)
    return out


def items(coll: dict, key: str) -> list:
    if not isinstance(coll, dict):
        return []
    return [v[key] for k, v in coll.items() if k != "count" and isinstance(v, dict) and key in v]
