#!/usr/bin/env python3
"""Push homeassistant/dashboards/counter.yaml to Home Assistant as the storage-mode dashboard
"dashboard-counter", then (optionally) reload the counter display.

    python3 homeassistant/scripts/push_dashboard.py [--url-path dashboard-counter] [--no-reload]
    python3 homeassistant/scripts/push_dashboard.py --backup out.json   # save the current config first

Needs `pip install websockets pyyaml`. Token and URL: see ha_api.py. The reload uses the tablet
API: counter_display_token / counter_display_api from android/keystore/ha-secrets.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

try:
    import websockets
except ImportError:
    sys.exit("pip install websockets")

DASHBOARD = ha_api.REPO / "homeassistant" / "dashboards" / "counter.yaml"


async def ws_call(messages: list[dict]) -> list[dict]:
    """Authenticate once and run each message in turn, returning the results."""
    results = []
    async with websockets.connect(ha_api.websocket_url(), ssl=ha_api.ssl_context(), max_size=50_000_000) as ws:
        assert json.loads(await ws.recv())["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": ha_api.token()}))
        reply = json.loads(await ws.recv())
        if reply["type"] != "auth_ok":
            sys.exit(f"websocket auth failed: {reply}")
        for i, msg in enumerate(messages, start=1):
            await ws.send(json.dumps({**msg, "id": i}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == i:
                    break
            if not r.get("success"):
                sys.exit(f"{msg['type']} failed: {r.get('error')}")
            results.append(r.get("result"))
    return results


def reload_tablet() -> None:
    text = ha_api.SECRETS.read_text() if ha_api.SECRETS.exists() else ""
    tok = re.search(r'^counter_display_token:\s*"?([^"\n]+?)"?\s*$', text, re.M)
    api = re.search(r'^counter_display_api:\s*"?([^"\n]+?)"?\s*$', text, re.M)
    if not (tok and api):
        print("tablet not reloaded: counter_display_token/api not in ha-secrets.yaml")
        return
    url = api.group(1).replace("{{ path }}", "reload")
    req = urllib.request.Request(url, method="POST", headers={"Authorization": tok.group(1)})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            print(f"tablet reload -> {r.status}")
    except Exception as e:  # noqa: BLE001
        print(f"tablet reload failed ({e}); it picks the change up on its next load")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-path", default="dashboard-counter")
    ap.add_argument("--file", type=Path, default=DASHBOARD)
    ap.add_argument("--backup", type=Path, help="write the dashboard's current config here first")
    ap.add_argument("--no-reload", action="store_true", help="don't tell the tablet to reload")
    args = ap.parse_args()

    config = yaml.safe_load(args.file.read_text())
    if not isinstance(config, dict) or not config.get("views"):
        sys.exit(f"{args.file}: no views found, nothing pushed")
    for key in [k for k in config if k.startswith("_")]:
        config.pop(key)  # YAML anchor scratch keys (_defs), not part of the dashboard
    views = config.get("views", [])
    print(f"{args.file.name}: {len(views)} views -> {args.url_path}")

    if args.backup:
        (current,) = asyncio.run(ws_call([{"type": "lovelace/config", "url_path": args.url_path, "force": False}]))
        args.backup.write_text(json.dumps(current, indent=1))
        print(f"backup written to {args.backup}")

    asyncio.run(ws_call([{"type": "lovelace/config/save", "url_path": args.url_path, "config": config}]))
    print("saved")
    if not args.no_reload:
        reload_tablet()


if __name__ == "__main__":
    main()
