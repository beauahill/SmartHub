#!/usr/bin/env python3
"""Make the counter display speak the same announcements as the Alexa "Everywhere" group.

    python3 homeassistant/scripts/setup_announcements.py [--dry-run]

Creates script.counter_announce (message [, volume]), which sends the text to Counter Home's
POST /say through rest_command.counter_display. The tablet reads it out with its own text-to-speech,
ducking whatever is playing, and raises the media volume to `volume` percent (default 40, never
above Counter Home's cap) for the announcement if it is lower.

Then, in every automation that announces to Alexa (notify.alexa_media targeting the Everywhere
group, or notify.alexa_media_everywhere_*), it adds a step right after that announcement which
starts script.counter_announce with the same message. The Alexa step itself is left as it was. The
new step uses script.turn_on, so it doesn't wait for the tablet, and continue_on_error, so an
offline tablet never stops the rest of the automation (the iPhone notifications, the thermostat).
Re-running is safe: automations that already call the script are skipped.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

SCRIPT_ID = "counter_announce"
SCRIPT_ENTITY = f"script.{SCRIPT_ID}"
EVERYWHERE = "media_player.everywhere_2"

SCRIPT = {
    "alias": "Counter display announcement",
    "description": "Speaks a message on the counter display (Counter Home POST /say). "
                   "Added next to the Alexa Everywhere announcements by setup_announcements.py.",
    "icon": "mdi:bullhorn",
    "mode": "queued",
    "max": 10,
    "fields": {
        "message": {"name": "Message", "required": True, "selector": {"text": {}}},
        "volume": {
            "name": "Minimum volume",
            "description": "Media volume (percent) for the announcement if it is lower. Never above the cap.",
            "default": 40,
            "selector": {"number": {"min": 0, "max": 100, "unit_of_measurement": "%"}},
        },
    },
    "sequence": [
        {
            "action": "rest_command.counter_display",
            "data": {"path": "say?volume={{ volume | default(40) | int }}&text={{ message | urlencode }}"},
            "continue_on_error": True,
        }
    ],
}


def action_name(step: dict) -> str:
    return step.get("action") or step.get("service") or ""


def alexa_message(step: dict) -> str | None:
    """The spoken text if this step is an Alexa Everywhere announcement, else None."""
    name = action_name(step)
    data = step.get("data") or {}
    if name.startswith("notify.alexa_media_everywhere"):
        return data.get("message")
    if name == "notify.alexa_media":
        target = data.get("target") or []
        if isinstance(target, str):
            target = [target]
        if EVERYWHERE in target:
            return data.get("message")
    return None


def counter_step(message: str) -> dict:
    return {
        "action": "script.turn_on",
        "target": {"entity_id": SCRIPT_ENTITY},
        "data": {"variables": {"message": message}},
        "continue_on_error": True,
    }


def add_steps(actions: list) -> int:
    """Inserts a counter step after each Alexa announcement, recursing into nested sequences."""
    added = 0
    i = 0
    while i < len(actions):
        step = actions[i]
        if isinstance(step, dict):
            for key in ("sequence", "then", "else", "default"):
                if isinstance(step.get(key), list):
                    added += add_steps(step[key])
            for opt in step.get("choose") or []:
                if isinstance(opt, dict) and isinstance(opt.get("sequence"), list):
                    added += add_steps(opt["sequence"])
            msg = alexa_message(step)
            if msg:
                actions.insert(i + 1, counter_step(msg))
                added += 1
                i += 1
        i += 1
    return added


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args()

    if not args.dry_run:
        ha_api.post(f"/api/config/script/config/{SCRIPT_ID}", SCRIPT)
        print(f"saved {SCRIPT_ENTITY}")

    for state in ha_api.get("/api/states"):
        if not state["entity_id"].startswith("automation."):
            continue
        aid = state["attributes"].get("id")
        if not aid:
            continue
        try:
            cfg = ha_api.get(f"/api/config/automation/config/{aid}")
        except SystemExit:
            continue  # YAML-only automation, not editable through the API
        if SCRIPT_ENTITY in json.dumps(cfg):
            print(f"   already done  {cfg.get('alias')}")
            continue
        key = "actions" if "actions" in cfg else "action"
        new = copy.deepcopy(cfg)
        acts = new.get(key)
        if not isinstance(acts, list):
            acts = [acts] if isinstance(acts, dict) else []
            new[key] = acts
        n = add_steps(acts)
        if not n:
            continue
        print(f"   {'would add' if args.dry_run else 'added'} {n} step(s)  {cfg.get('alias')}")
        if not args.dry_run:
            ha_api.post(f"/api/config/automation/config/{aid}", new)


if __name__ == "__main__":
    main()
