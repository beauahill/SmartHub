"""Small helper for talking to Home Assistant from the repo scripts.

Configuration, in order of precedence:
  HA_URL    (default https://192.168.0.137:8123)
  HA_TOKEN  a long-lived access token; if unset, read `ha_token:` from
            android/keystore/ha-secrets.yaml (git-ignored)
  HA_VERIFY_SSL=0 to skip certificate checks (the default when HA_URL is an IP address, since a
            Let's Encrypt certificate is issued for the public name, not the LAN IP)
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SECRETS = REPO / "android" / "keystore" / "ha-secrets.yaml"

URL = os.environ.get("HA_URL", "https://192.168.0.137:8123").rstrip("/")


def _host_is_ip(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


VERIFY_SSL = os.environ.get("HA_VERIFY_SSL", "0" if _host_is_ip(URL) else "1") != "0"


def token() -> str:
    tok = os.environ.get("HA_TOKEN")
    if tok:
        return tok
    if SECRETS.exists():
        m = re.search(r'^ha_token:\s*"?([^"\s]+)"?', SECRETS.read_text(), re.M)
        if m:
            return m.group(1)
    sys.exit(f"No Home Assistant token: set HA_TOKEN or add ha_token: to {SECRETS}")


def ssl_context() -> ssl.SSLContext | None:
    if VERIFY_SSL:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def request(method: str, path: str, body=None, timeout: int = 30):
    """REST call against /api/...; returns parsed JSON (or None for an empty body)."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        URL + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {detail}") from None
    return json.loads(raw) if raw else None


def get(path: str, **kw):
    return request("GET", path, **kw)


def post(path: str, body=None, **kw):
    return request("POST", path, body, **kw)


def websocket_url() -> str:
    scheme = "wss" if URL.startswith("https") else "ws"
    return scheme + URL[URL.index("://"):] + "/api/websocket"
