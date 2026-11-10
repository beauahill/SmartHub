#!/usr/bin/env python3
"""Prepare Home Assistant for the counter display's hands-free voice. Safe to re-run.

    python3 homeassistant/scripts/setup_voice.py [--wake-word okay_nabu]

1. Installs and starts the openWakeWord add-on (Home Assistant OS / Supervised only) and adds its
   Wyoming integration, which gives wake_word.openwakeword.
2. Puts that wake word on the preferred Assist pipeline (the tablet uses the preferred pipeline
   unless Counter Home's "voicePipeline" setting names another).
3. Creates one script per dock tile (Radio, Spotify, YouTube TV, IPTV, Counter dashboard) so
   "turn on <app>" opens it on the tablet, exposes them and the hub's Spotify player to Assist, and
   gives the gate, garage doors, locks and sensors short aliases so "open the gate" just works.

Needs `pip install websockets`; token and URL as in ha_api.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402
from push_dashboard import ws_call  # noqa: E402

ADDON = "core_openwakeword"

ALIASES = {
    "cover.gate_switch_gate": ["gate", "the gate", "driveway gate"],
    "switch.garage_opener_single": ["single garage door", "small garage door", "single garage"],
    "switch.garage_opener_double": ["double garage door", "big garage door", "double garage"],
    "lock.w_garage_entry_deadbolt": ["garage door lock", "west garage lock", "garage entry"],
    "lock.touchscreen_deadbolt_z_wave_plus": ["back door", "back porch door", "back porch lock"],
    "switch.fireplace_switch_fireplace_switch": ["fireplace"],
    "fan.hot_tub_jets_1": ["hot tub jets", "jets"],
    "switch.hot_tub_lights": ["hot tub lights"],
    "light.man_cave": ["man cave lights"],
    "switch.front_porch": ["front porch lights", "porch lights"],
    # Questions: "what is the outside temperature", "how warm is the hot tub", "what's the weather"
    "sensor.main_outdoor_temperature_2": ["outside temperature", "outdoor temperature", "temperature outside"],
    "sensor.hot_tub_current_temperature": ["hot tub temperature", "hot tub water temperature"],
    "sensor.main_thermostat_humidity_2": ["indoor humidity", "humidity inside"],
    "climate.main": ["thermostat", "house thermostat", "heat"],
    "weather.kgcc_daynight": ["weather", "gillette weather"],
}

# One script per dock tile, so "turn on <name>" opens the app on the tablet. The spoken aliases are
# set on the script entities below (SCRIPT_ALIASES); the path is the tile label in Counter Home.
SCRIPTS = {
    "counter_radio": {
        "alias": "Radio",
        "icon": "mdi:radio",
        "description": "Opens the Radio (Audacy) tile on the counter display. Say: turn on the radio.",
        "sequence": [{"action": "rest_command.counter_display", "data": {"path": "launch?app=Radio"}}],
        "mode": "single",
    },
    "counter_music": {
        "alias": "Spotify",
        "icon": "mdi:spotify",
        "description": "Opens the Music (Spotify) tile on the counter display. Say: turn on Spotify.",
        "sequence": [{"action": "rest_command.counter_display", "data": {"path": "launch?app=Music"}}],
        "mode": "single",
    },
    "counter_live_tv": {
        "alias": "YouTube TV",
        "icon": "mdi:youtube-tv",
        "description": "Opens the Live TV (YouTube TV) tile on the counter display. Say: turn on YouTube TV.",
        "sequence": [{"action": "rest_command.counter_display", "data": {"path": "launch?app=Live TV"}}],
        "mode": "single",
    },
    "counter_iptv": {
        "alias": "IPTV",
        "icon": "mdi:television-classic",
        "description": "Opens the IPTV tile on the counter display. Say: turn on IPTV.",
        "sequence": [{"action": "rest_command.counter_display", "data": {"path": "launch?app=IPTV"}}],
        "mode": "single",
    },
    "counter_dashboard": {
        "alias": "Counter dashboard",
        "icon": "mdi:tablet-dashboard",
        "description": "Brings the counter display back to its dashboard. Say: turn on the counter dashboard.",
        "sequence": [{"action": "rest_command.counter_display", "data": {"path": "home"}}],
        "mode": "single",
    },
}

# Assist's built-in matcher only reliably matches scripts by alias, so the names are repeated here.
SCRIPT_ALIASES = {
    "script.counter_radio": ["radio", "the radio", "Audacy"],
    "script.counter_music": ["Spotify", "music", "the music app", "Spotify on the hub"],
    "script.counter_live_tv": ["YouTube TV", "live TV", "YouTube TV on the hub"],
    "script.counter_iptv": ["IPTV", "Telvizio", "the IPTV app"],
    "script.counter_dashboard": ["counter dashboard", "the dashboard", "the hub dashboard", "the counter display"],
}

# Spotify sees the tablet as a Connect device, so the built-in media sentences ("pause the hub",
# "next song on the hub", "set the hub volume to 40") work once the player is exposed.
MEDIA_PLAYERS = {
    "media_player.spotify_beauhill": ["the hub", "hub music", "kitchen music", "the counter speaker"],
}


def supervisor(endpoint: str, method: str = "get", data: dict | None = None, timeout: int = 60):
    msg = {"type": "supervisor/api", "endpoint": endpoint, "method": method, "timeout": timeout}
    if data is not None:
        msg["data"] = data
    (r,) = asyncio.run(ws_call([msg]))
    return r.get("data", r) if isinstance(r, dict) else r


def wake_word_entity() -> str | None:
    for e in ha_api.get("/api/states"):
        if e["entity_id"].startswith("wake_word."):
            return e["entity_id"]
    return None


def step_addon() -> None:
    comps = ha_api.get("/api/config")["components"]
    if "hassio" not in comps:
        print("  no Supervisor: install openWakeWord (or any Wyoming wake word service) by hand")
        return
    info = supervisor(f"/addons/{ADDON}/info")
    if info.get("state") == "started":
        print("  openWakeWord add-on already running")
    else:
        if not info.get("version"):
            print("  installing openWakeWord add-on (a few minutes on a Pi)...")
            supervisor(f"/store/addons/{ADDON}/install", "post", timeout=900)
        print("  starting openWakeWord add-on")
        supervisor(f"/addons/{ADDON}/options", "post", {"boot": "auto", "watchdog": True})
        supervisor(f"/addons/{ADDON}/start", "post", timeout=300)
        time.sleep(5)

    entries = ha_api.get("/api/config/config_entries/entry?domain=wyoming")
    if any("openwakeword" in e["title"].lower() for e in entries):
        print("  Wyoming entry for openWakeWord exists")
    else:
        # The add-on announces itself to Home Assistant; finish the discovered flow if there is one,
        # otherwise add it by its internal hostname.
        (progress,) = asyncio.run(ws_call([{"type": "config_entries/flow/progress"}]))
        flows = [f for f in progress if f.get("handler") == "wyoming"]
        if flows:
            r = ha_api.post(f"/api/config/config_entries/flow/{flows[0]['flow_id']}", {})
        else:
            f = ha_api.post("/api/config/config_entries/flow", {"handler": "wyoming"})
            r = ha_api.post(f"/api/config/config_entries/flow/{f['flow_id']}", {"host": "core-openwakeword", "port": 10400})
        print(f"  Wyoming: {r.get('type')} {r.get('title', r.get('reason', ''))}")
        time.sleep(3)


def step_agent(agent: str) -> None:
    """Make [agent] (a conversation.* entity, e.g. Claude) the pipeline's brain, with built-in
    sentences tried first so device commands stay instant and free."""
    if not any(s["entity_id"] == agent for s in ha_api.get("/api/states")):
        sys.exit(f"  no such conversation agent: {agent}")
    (lst,) = asyncio.run(ws_call([{"type": "assist_pipeline/pipeline/list"}]))
    pipeline = next(p for p in lst["pipelines"] if p["id"] == lst["preferred_pipeline"])
    if pipeline.get("conversation_engine") == agent and pipeline.get("prefer_local_intents"):
        print(f"  pipeline '{pipeline['name']}' already uses {agent}")
        return
    fields = ["name", "language", "conversation_language", "stt_engine", "stt_language",
              "tts_engine", "tts_language", "tts_voice", "wake_word_entity", "wake_word_id"]
    msg = {"type": "assist_pipeline/pipeline/update", "pipeline_id": pipeline["id"],
           **{k: pipeline.get(k) for k in fields if k in pipeline},
           "conversation_engine": agent, "prefer_local_intents": True}
    asyncio.run(ws_call([msg]))
    print(f"  pipeline '{pipeline['name']}': conversation agent {agent}, local sentences first")


def step_pipeline(wake_word_id: str) -> None:
    ww = wake_word_entity()
    if not ww:
        print("  no wake_word entity yet; re-run once the openWakeWord add-on is up")
        return
    (info,) = asyncio.run(ws_call([{"type": "wake_word/info", "entity_id": ww}]))
    ids = {w["id"]: w["name"] for w in info["wake_words"]}
    if wake_word_id not in ids:
        sys.exit(f"  {ww} offers {', '.join(ids)}; '{wake_word_id}' is not one of them")
    (lst,) = asyncio.run(ws_call([{"type": "assist_pipeline/pipeline/list"}]))
    pipeline = next(p for p in lst["pipelines"] if p["id"] == lst["preferred_pipeline"])
    if pipeline.get("wake_word_entity") == ww and pipeline.get("wake_word_id") == wake_word_id:
        print(f"  pipeline '{pipeline['name']}' already uses {ww} / {wake_word_id}")
        return
    fields = ["name", "language", "conversation_engine", "conversation_language", "stt_engine", "stt_language",
              "tts_engine", "tts_language", "tts_voice", "prefer_local_intents"]
    msg = {"type": "assist_pipeline/pipeline/update", "pipeline_id": pipeline["id"],
           **{k: pipeline.get(k) for k in fields if k in pipeline},
           "wake_word_entity": ww, "wake_word_id": wake_word_id}
    asyncio.run(ws_call([msg]))
    print(f"  pipeline '{pipeline['name']}': wake word {wake_word_id} on {ww}")


def step_scripts_and_aliases() -> None:
    for sid, body in SCRIPTS.items():
        ha_api.post(f"/api/config/script/config/{sid}", body)
        print(f"  script.{sid} ({body['alias']})")
    time.sleep(3)  # saving scripts reloads them; aliases set during the reload are lost
    everything = {**ALIASES, **SCRIPT_ALIASES, **MEDIA_PLAYERS}
    msgs = [{"type": "config/entity_registry/update", "entity_id": e, "aliases": a} for e, a in everything.items()]
    results = asyncio.run(ws_call(msgs))
    print(f"  aliases set on {len(results)} entities")
    asyncio.run(ws_call([{"type": "homeassistant/expose_entity", "assistants": ["conversation"],
                          "entity_ids": list(everything), "should_expose": True}]))
    print(f"  {len(everything)} entities exposed to Assist")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wake-word", default="okay_nabu", help="okay_nabu, hey_jarvis, alexa, hey_mycroft or hey_rhasspy")
    ap.add_argument("--conversation-agent", metavar="ENTITY",
                    help="conversation.* entity to answer with, e.g. conversation.claude_conversation (Anthropic integration)")
    args = ap.parse_args()
    print("Wake word service"); step_addon()
    print("Assist pipeline"); step_pipeline(args.wake_word)
    if args.conversation_agent:
        print("Conversation agent"); step_agent(args.conversation_agent)
    print("Scripts and aliases"); step_scripts_and_aliases()


if __name__ == "__main__":
    main()
