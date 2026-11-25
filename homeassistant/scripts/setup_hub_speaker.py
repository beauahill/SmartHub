#!/usr/bin/env python3
"""Reopen MassDroid when the hub drops out of Music Assistant.

    python3 homeassistant/scripts/setup_hub_speaker.py [--dry-run] [--player-id ID | --entity ENTITY]

MassDroid makes the tablet a Music Assistant speaker ("Counter Display"), which is what lets anyone
on the Wi-Fi pick the hub in Spotify or AirPlay to it. When MassDroid's process restarts without
its screen being opened (killed, crashed, tablet reboot), Counter Home brings its playback service
back, but the service alone never signs in to Music Assistant, so the hub vanishes from Spotify and
AirPlay. Opening MassDroid once makes it sign in again.

This saves one UI automation (editable in Settings > Automations) that does that:

  * When the player's media_player entity has been unavailable for 5 minutes (Music Assistant
    takes about 3 minutes to notice a drop, so that is about 8 minutes after it), it waits until
    the dashboard is in front or the panel is off, opens MassDroid for 10 seconds, goes back to
    the dashboard and puts the screen back the way it was (off, or on the clock). It never
    interrupts an app someone has open; it waits for them to leave it.
  * It tries up to 3 times, 15 minutes apart, then leaves one notification in Home Assistant.
    It does the same if the tablet stays unreachable or busy for a day. The notification clears
    when the player is back.

Needs:
  * "Expose this player to Home Assistant" switched on for the player in Music Assistant
    (Settings > Players), so Home Assistant has an entity to watch. The script finds the entity by
    the Music Assistant player id and writes nothing if there isn't one.
  * Counter Home 1.9.3 or later. Earlier versions refuse to open MassDroid while the kiosk lock is
    on, because it isn't a dock tile.

Re-running replaces the automation with the version below.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

# Music Assistant's id for the tablet's MassDroid (Sendspin) player; it survives renames.
PLAYER_ID = "HykSypy9KKUSS8N_N-4V0TZW3Bbo2WuZTP4W78GYw2k"
APP = "net.asksakis.massdroidv2"
AUTOMATION_ID = "counter_display_hub_speaker_reconnect"
NOTIFICATION_ID = "counter_display_hub_speaker"
ATTEMPTS = 3

SCREEN = "binary_sensor.counter_display_screen"
ON_DASHBOARD = "binary_sensor.counter_display_on_dashboard"
LAUNCHER = "binary_sensor.counter_display_launcher_in_front"
TABLET = "sensor.counter_display_battery"


def find_entity(player_id: str) -> str | None:
    """The media_player the Music Assistant integration made for this player, if it made one."""
    template = (
        "{% set ns = namespace(found=[]) %}"
        "{% for e in integration_entities('music_assistant') if e.startswith('media_player.') %}"
        "{% if (device_attr(e, 'identifiers') | string).find(\"'\" ~ pid ~ \"'\") >= 0 %}"
        "{% set ns.found = ns.found + [e] %}{% endif %}{% endfor %}"
        "{{ ns.found | to_json }}"
    )
    found = ha_api.post("/api/template", {"template": template, "variables": {"pid": player_id}})
    return found[0] if found else None


def rest(path: str) -> dict:
    # continue_on_error: a tablet that misses one call must not stop the steps that put the screen back.
    return {"action": "rest_command.counter_display", "data": {"path": path}, "continue_on_error": True}


def automation(player: str, player_id: str = PLAYER_ID) -> dict:
    missing = "{{ is_state('" + player + "', 'unavailable') }}"
    back = "{{ not is_state('" + player + "', 'unavailable') }}"
    # Don't bother the tablet unless it can help: Music Assistant has to be up (some other player of
    # its is available), the tablet has to answer, and nobody may have an app open. The launcher
    # sensor reads off while the panel is off, so a dark panel counts as free too; otherwise a drop
    # late in the evening would wait for the morning.
    ready = (
        "{{ (is_state('" + LAUNCHER + "', 'on') or is_state('" + SCREEN + "', 'off'))"
        " and states('" + TABLET + "') not in ['unavailable', 'unknown']"
        " and integration_entities('music_assistant') | select('match', 'media_player\\\\.')"
        " | reject('eq', '" + player + "') | reject('is_state', 'unavailable') | list | count > 0 }}"
    )
    notify = {
        "action": "persistent_notification.create",
        "data": {
            "notification_id": NOTIFICATION_ID,
            "title": "The hub speaker is missing from Music Assistant",
            "message": (
                "Counter Display is still unavailable, so the hub won't show up in Spotify or "
                f"AirPlay. Home Assistant reopens MassDroid on the tablet up to {ATTEMPTS} times when "
                "this happens; that didn't bring it back, or the tablet couldn't be reached. Open "
                "MassDroid (the Speakers tile) and check it is signed in to Music Assistant. This "
                "clears by itself when the player is back."
            ),
        },
    }
    attempt = [
        {"condition": "template", "value_template": missing},
        {"wait_template": ready, "timeout": "24:00:00", "continue_on_timeout": True},
        # Never became free: say so instead of ending quietly with the speaker still missing.
        {"if": [{"condition": "template", "value_template": "{{ not wait.completed }}"}],
         "then": [notify, {"stop": "The tablet stayed unreachable or busy for a day"}]},
        {"condition": "template", "value_template": missing},
        {"variables": {
            "screen_was_on": "{{ is_state('" + SCREEN + "', 'on') }}",
            # The launcher is in front here (see `ready`), so "not on the dashboard" means the clock.
            "clock_was_on": "{{ is_state('" + SCREEN + "', 'on') and is_state('" + LAUNCHER + "', 'on')"
                            " and is_state('" + ON_DASHBOARD + "', 'off') }}",
        }},
        rest(f"launch?app={APP}"),
        {"delay": "00:00:10"},   # it signs in about 2 seconds after opening
        rest("home?media=keep"),
        {"delay": "00:00:02"},
        {"choose": [
            {"conditions": [{"condition": "template", "value_template": "{{ not screen_was_on }}"}],
             "sequence": [rest("screen/off")]},
            {"conditions": [{"condition": "template", "value_template": "{{ clock_was_on }}"}],
             "sequence": [rest("ambient/on")]},
        ]},
        {"wait_template": back, "timeout": "00:03:00", "continue_on_timeout": True},
        {"if": [{"condition": "template", "value_template": missing}],
         "then": [{"delay": "00:15:00"}]},
    ]
    return {
        "alias": "Counter display, reopen MassDroid when the hub speaker drops out",
        "description": (
            f"Watches {player} (Music Assistant player {player_id}). "
            "Saved by setup_hub_speaker.py; see the README, \"Spotify Connect and AirPlay for everyone\"."
        ),
        "mode": "single",
        "max_exceeded": "silent",
        "triggers": [
            {"trigger": "state", "entity_id": player, "to": "unavailable", "for": "00:05:00", "id": "missing"},
            # After a restart the entity can start out unavailable without ever changing to it.
            {"trigger": "homeassistant", "event": "start", "id": "start"},
            {"trigger": "state", "entity_id": player, "from": "unavailable", "id": "back"},
        ],
        "conditions": [],
        "actions": [
            {"choose": [
                {
                    "conditions": [{"condition": "trigger", "id": "back"}],
                    "sequence": [{"action": "persistent_notification.dismiss",
                                  "data": {"notification_id": NOTIFICATION_ID}}],
                },
            ], "default": [
                {"if": [{"condition": "trigger", "id": "start"}], "then": [{"delay": "00:10:00"}]},
                # Each attempt ends the loop by itself (a failed condition) once the player is back.
                {"repeat": {"count": ATTEMPTS, "sequence": attempt}},
                {"if": [{"condition": "template", "value_template": missing}],
                 "then": [notify],
                 "else": [{"action": "persistent_notification.dismiss",
                           "data": {"notification_id": NOTIFICATION_ID}}]},
            ]},
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the automation, write nothing")
    ap.add_argument("--player-id", default=PLAYER_ID, help="Music Assistant player id of the tablet")
    ap.add_argument("--entity", help="skip the lookup and watch this media_player entity")
    args = ap.parse_args()

    player = args.entity or find_entity(args.player_id)
    if not player:
        sys.exit(
            f"Home Assistant has no media_player for Music Assistant player {args.player_id}.\n"
            "In Music Assistant open Settings > Players > Counter Display and switch on\n"
            "\"Expose this player to Home Assistant\", then run this again. Nothing was written."
        )
    cfg = automation(player, args.player_id)
    if args.dry_run:
        print(json.dumps({AUTOMATION_ID: cfg}, indent=1))
        return
    ha_api.post(f"/api/config/automation/config/{AUTOMATION_ID}", cfg)
    print(f"saved {cfg['alias']} (watching {player})")


if __name__ == "__main__":
    main()
