#!/usr/bin/env python3
"""Keep the counter display sensible when the presence radar isn't reporting.

    python3 homeassistant/scripts/setup_presence_fallbacks.py [--dry-run]

Every screen automation in packages/counter_display.yaml is triggered by
binary_sensor.counter_presence_presence. If the LD2410C stops talking to the ESP32 (it sits at
unknown/unavailable), none of them run: the panel stays on at whatever brightness it last had,
the clock never comes up, and the tablet can use more power than its 5 V supply delivers.

This saves three UI automations (editable in Settings > Automations) that don't depend on the radar:

  * Brightness by time of day: 25 from 22:00 to 06:00, auto otherwise. Applied at 22:00, 06:00,
    Home Assistant start and whenever the panel turns on, so it holds whether or not the radar works.
  * Clock fallback: only while the radar is down, the sleep screen comes up after the dashboard has
    been in front for 10 minutes (tap to dismiss; it comes back 10 minutes later). The panel is never
    turned off this way, because with the radar down nothing could wake it again.
  * Radar alert: a persistent notification in Home Assistant when the radar has been down for
    30 minutes (and each morning at 09:00 while it stays down), dismissed when it reports again.

Re-running replaces them with the versions below.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

PRESENCE = "binary_sensor.counter_presence_presence"
RADAR_DOWN = "{{ states('" + PRESENCE + "') in ['unknown', 'unavailable'] }}"
NOTIFICATION_ID = "counter_presence_down"

AUTOMATIONS = {
    "counter_display_brightness_schedule": {
        "alias": "Counter display, brightness by time of day",
        "description": "25 from 22:00 to 06:00, auto otherwise. Doesn't need the presence radar. "
                       "Saved by setup_presence_fallbacks.py.",
        "mode": "single",
        "triggers": [
            {"trigger": "time", "at": "22:00:00"},
            {"trigger": "time", "at": "06:00:00"},
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "state", "entity_id": "binary_sensor.counter_display_screen", "from": "off", "to": "on"},
        ],
        "conditions": [],
        "actions": [
            {
                "action": "rest_command.counter_display",
                "data": {
                    "path": "{{ 'brightness?value=25' if now().hour >= 22 or now().hour < 6 "
                            "else 'brightness?value=auto' }}"
                },
                "continue_on_error": True,
            }
        ],
    },
    "counter_display_clock_fallback": {
        "alias": "Counter display, clock after 10 minutes while the radar is down",
        "description": "Stands in for the 2-minute clock automation when the presence radar isn't "
                       "reporting. Saved by setup_presence_fallbacks.py.",
        "mode": "single",
        "triggers": [
            {"trigger": "state", "entity_id": "binary_sensor.counter_display_on_dashboard",
             "to": "on", "for": "00:10:00"},
            {"trigger": "state", "entity_id": PRESENCE, "to": ["unknown", "unavailable"],
             "for": "00:10:00"},
        ],
        "conditions": [
            {"condition": "template", "value_template": RADAR_DOWN},
            {"condition": "state", "entity_id": "binary_sensor.counter_display_on_dashboard",
             "state": "on", "for": "00:10:00"},
        ],
        "actions": [
            {"action": "rest_command.counter_display", "data": {"path": "ambient/on"},
             "continue_on_error": True}
        ],
    },
    "counter_display_radar_alert": {
        "alias": "Counter display, warn when the presence radar stops reporting",
        "description": "Persistent notification while binary_sensor.counter_presence_presence is "
                       "unknown/unavailable. Saved by setup_presence_fallbacks.py.",
        "mode": "single",
        "triggers": [
            {"trigger": "state", "entity_id": PRESENCE, "to": ["unknown", "unavailable"],
             "for": "00:30:00", "id": "down"},
            {"trigger": "time", "at": "09:00:00", "id": "down"},
            {"trigger": "state", "entity_id": PRESENCE, "to": ["on", "off"], "id": "up"},
        ],
        "conditions": [],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [
                            {"condition": "trigger", "id": "down"},
                            {"condition": "template", "value_template": RADAR_DOWN},
                        ],
                        "sequence": [
                            {
                                "action": "persistent_notification.create",
                                "data": {
                                    "notification_id": NOTIFICATION_ID,
                                    "title": "Counter display presence radar isn't reporting",
                                    "message": (
                                        "binary_sensor.counter_presence_presence reads "
                                        "{{ states('" + PRESENCE + "') }}. The display won't wake, "
                                        "show the clock after 2 minutes or turn off at night until it "
                                        "reports again; the fallbacks keep brightness on schedule and "
                                        "bring the clock up after 10 minutes. Check the LD2410C wiring "
                                        "(see the README)."
                                    ),
                                },
                            }
                        ],
                    },
                    {
                        "conditions": [{"condition": "trigger", "id": "up"}],
                        "sequence": [
                            {"action": "persistent_notification.dismiss",
                             "data": {"notification_id": NOTIFICATION_ID}}
                        ],
                    },
                ]
            }
        ],
    },
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the automations, write nothing")
    args = ap.parse_args()
    for aid, cfg in AUTOMATIONS.items():
        if args.dry_run:
            print(json.dumps({aid: cfg}, indent=1))
            continue
        ha_api.post(f"/api/config/automation/config/{aid}", cfg)
        print(f"saved {cfg['alias']}")


if __name__ == "__main__":
    main()
