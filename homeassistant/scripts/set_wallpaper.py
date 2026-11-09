#!/usr/bin/env python3
"""Upload the dashboard wallpaper to Home Assistant and point every view of counter.yaml at it.

    python3 homeassistant/dashboards/wallpaper/make_wallpaper.py      # render the PNG (optional)
    python3 homeassistant/scripts/set_wallpaper.py [image.png]        # upload + rewrite counter.yaml
    python3 homeassistant/scripts/push_dashboard.py                   # publish

The picture goes into HA's image store (Settings > Dashboards > Pictures), served without a login
at /api/image/serve/<id>/original, so the kiosk's "counter" user can load it. A previous wallpaper
uploaded by this script is deleted from the store first.
"""

from __future__ import annotations

import json
import mimetypes
import re
import sys
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

DASHBOARD = ha_api.REPO / "homeassistant" / "dashboards" / "counter.yaml"
DEFAULT_IMAGE = ha_api.REPO / "homeassistant" / "dashboards" / "wallpaper" / "counter_wallpaper.png"
BACKGROUND = """    background:
      image: {url}
      size: cover
      attachment: fixed
"""


def upload(path: Path) -> str:
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        ha_api.URL + "/api/image/upload",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {ha_api.token()}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=120, context=ha_api.ssl_context()) as r:
        return json.loads(r.read())["id"]


def main() -> None:
    image = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IMAGE
    text = DASHBOARD.read_text()

    old = set(re.findall(r"/api/image/serve/([0-9a-f]{32})/original", text))
    new_id = upload(image)
    url = f"/api/image/serve/{new_id}/original"
    print(f"uploaded {image.name} -> {url}")

    # Replace an existing background image, or add a background block to each view.
    if old:
        for oid in old:
            text = text.replace(f"/api/image/serve/{oid}/original", url)
        try:
            from push_dashboard import ws_call  # deleting from the image store is websocket-only

            import asyncio

            asyncio.run(ws_call([{"type": "image/delete", "image_id": oid} for oid in old]))
            print(f"deleted previous wallpaper(s): {', '.join(sorted(old))}")
        except SystemExit as e:  # already gone; harmless
            print(f"  (previous wallpaper not deleted: {e})")
    else:
        text, n = re.subn(r"(    dense_section_placement: true\n)", r"\1" + BACKGROUND.format(url=url), text)
        print(f"background added to {n} views")
    DASHBOARD.write_text(text)
    print(f"{DASHBOARD.name} updated; run push_dashboard.py to publish")


if __name__ == "__main__":
    main()
