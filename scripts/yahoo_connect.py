"""One-time: trade the code the league member got from Yahoo ("Agree" page) for a refresh token.

Run by the 'Connect Yahoo league' workflow with the code as input. The code works once and expires
in about 10 minutes. Writes data/private/yahoo_token.enc (encrypted).
"""
from __future__ import annotations

import os

from yahoo_common import save_token, token_request

code = os.environ.get("YAHOO_CODE", "").strip()
if not code:
    raise SystemExit("No code given")
tok = token_request({"grant_type": "authorization_code", "code": code})
save_token(tok)
print("[yahoo] connected: token saved (encrypted)")
