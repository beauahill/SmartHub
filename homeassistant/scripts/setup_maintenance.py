#!/usr/bin/env python3
"""Set up home maintenance tracking in Home Assistant from homeassistant/maintenance/tasks.yaml.
Safe to re-run after editing the task list: existing due dates are kept.

    python3 homeassistant/scripts/setup_maintenance.py [--prune]

What it creates, all through the API (no file access to the HA config folder needed):
  calendar.home_maintenance               a Local Calendar: the permanent log of what was done when
  input_datetime.maint_<task>             one per task, the date it is next DUE ("Furnace filter due")
  input_number.maint_tub_<reading>        the latest hot tub water test (free chlorine, pH, ...)
  script.maint_done                       task [, date, note]: moves the due date on, logs it
  script.maint_snooze                     task [, days]: due again in N days (default 7)
  script.maint_log_water_test             [fc, ph, ta, ch, salt]: saves the readings, logs the test
  script.maint_tub_dose                   chemical [, amount]: logs what went into the hot tub
  automation.home_maintenance_reminders   9:00 nudge for anything due today (Done / Snooze buttons),
                                          and a Saturday digest of overdue / due this week
  automation.home_maintenance_reminder_buttons   handles those buttons
and exposes the scripts, dates, readings and calendar to Assist, so "I changed the furnace filter"
or "when is the sprinkler blowout due?" work by voice.

A date helper can't be empty, so a task with no date yet holds NOT_SET (2000-01-01): the dashboard
shows it as "Not set", reminders skip it. New helpers start at NOT_SET, or at the next MM-DD for a
seasonal task. --prune deletes maint_* date helpers whose task is no longer in tasks.yaml.
Needs `pip install websockets pyyaml`; token and URL as in ha_api.py.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402
from push_dashboard import ws_call  # noqa: E402

TASKS_FILE = ha_api.REPO / "homeassistant" / "maintenance" / "tasks.yaml"
DASHBOARD = ha_api.REPO / "homeassistant" / "dashboards" / "counter.yaml"
CALENDAR_TITLE = "Home Maintenance"
CALENDAR = "calendar.home_maintenance"
NOT_SET = "2000-01-01"  # "no date yet"; must match counter.yaml (upkeep templates)

ASSIST_ALIASES = {
    "script.maint_done": ["record maintenance", "mark maintenance done", "log maintenance", "maintenance done"],
    "script.maint_snooze": ["snooze maintenance", "postpone maintenance"],
    "script.maint_log_water_test": ["log hot tub water test", "hot tub test results", "hot tub readings"],
    "script.maint_tub_dose": ["log hot tub chemicals", "hot tub chemicals added"],
    CALENDAR: ["maintenance log", "home maintenance log"],
}


def load() -> dict:
    cfg = yaml.safe_load(TASKS_FILE.read_text())
    for tid, t in cfg["tasks"].items():
        if ("every" in t) == ("season" in t):
            sys.exit(f"{TASKS_FILE.name}: task {tid} needs exactly one of 'every' or 'season'")
        if "season" in t:
            m, d = (int(x) for x in str(t["season"]).split("-"))
            if not (1 <= m <= 12 and 1 <= d <= 28):
                sys.exit(f"{TASKS_FILE.name}: task {tid} season must be MM-DD with a day of 28 or less")
        if t.get("category") not in cfg["categories"]:
            sys.exit(f"{TASKS_FILE.name}: task {tid} has unknown category {t.get('category')!r}")
    return cfg


# --------------------------------------------------------------------------------- calendar
def step_calendar() -> None:
    titles = {e["title"] for e in ha_api.get("/api/config/config_entries/entry?domain=local_calendar")}
    if CALENDAR_TITLE in titles:
        print(f"  exists  {CALENDAR}")
        return
    flow = ha_api.post("/api/config/config_entries/flow", {"handler": "local_calendar"})
    r = ha_api.post(f"/api/config/config_entries/flow/{flow['flow_id']}", {"calendar_name": CALENDAR_TITLE})
    if r.get("type") != "create_entry":
        sys.exit(f"  local_calendar flow did not finish: {r}")
    print(f"  created {CALENDAR}")


# --------------------------------------------------------------------------------- helpers
def sync_helpers(domain: str, wanted: dict[str, dict], prune_prefix: str | None) -> list[str]:
    """Create/update storage helpers so that <domain>.<id> exists for each id in wanted, with the
    given fields. The id comes from the name a helper is created with, so create it under its id
    and rename it afterwards (the entity id stays)."""
    (existing,) = asyncio.run(ws_call([{"type": f"{domain}/list"}]))
    have = {h["id"]: h for h in existing}
    msgs = []
    for hid, fields in wanted.items():
        if hid in have:
            current = {k: have[hid].get(k) for k in fields}
            if current != fields:
                msgs.append({"type": f"{domain}/update", f"{domain}_id": hid, **fields})
        else:
            msgs.append({"type": f"{domain}/create", **fields, "name": hid})
            msgs.append({"type": f"{domain}/update", f"{domain}_id": hid, **fields})
    if prune_prefix:
        for hid in have:
            if hid.startswith(prune_prefix) and hid not in wanted:
                msgs.append({"type": f"{domain}/delete", f"{domain}_id": hid})
                print(f"  deleting {domain}.{hid}")
    if msgs:
        results = asyncio.run(ws_call(msgs))
        for msg, res in zip(msgs, results):
            if msg["type"].endswith("/create") and res.get("id") != msg["name"]:
                sys.exit(f"  {domain} created as {res.get('id')!r}, expected {msg['name']!r}")
    created = sum(1 for m in msgs if m["type"].endswith("/create"))
    print(f"  {domain}: {len(wanted)} wanted, {created} created, {len(msgs) - 2 * created} updated/deleted")
    return [m["name"] for m in msgs if m["type"].endswith("/create")]


def first_due(task: dict) -> str:
    """Starting date for a new task: the next MM-DD for a seasonal one, else NOT_SET."""
    if "season" not in task:
        return NOT_SET
    today = date.today()
    m, d = (int(x) for x in str(task["season"]).split("-"))
    due = today.replace(month=m, day=d)
    return (due if due > today else due.replace(year=today.year + 1)).isoformat()


def step_helpers(cfg: dict, prune: bool) -> None:
    created = sync_helpers(
        "input_datetime",
        {f"maint_{tid}": {"name": f"{t['name']} due", "icon": t["icon"], "has_date": True, "has_time": False}
         for tid, t in cfg["tasks"].items()},
        "maint_" if prune else None,
    )
    # A new date helper starts at today's date, which would read as "due today".
    for hid in created:
        due = first_due(cfg["tasks"][hid.removeprefix("maint_")])
        ha_api.post("/api/services/input_datetime/set_datetime", {"entity_id": f"input_datetime.{hid}", "date": due})
        print(f"  input_datetime.{hid} starts at {due}{' (not set)' if due == NOT_SET else ''}")
    sync_helpers(
        "input_number",
        {f"maint_tub_{rid}": {"name": r["name"], "icon": r["icon"], "min": r["min"], "max": r["max"],
                              "step": r["step"], "mode": "box",
                              **({"unit_of_measurement": r["unit"]} if r["unit"] else {})}
         for rid, r in cfg["water"].items()},
        None,
    )


# --------------------------------------------------------------------------------- scripts
NEXT_DUE = (
    "{% set d = strptime(done, '%Y-%m-%d').date() %}"
    "{% if t.every is defined %}{{ (d + timedelta(days=t.every | int)).isoformat() }}"
    "{% else %}{% set md = t.season.split('-') %}{% set e = d + timedelta(days=90) %}"
    "{% set c = e.replace(month=md[0] | int, day=md[1] | int) %}"
    "{{ (c if c >= e else c.replace(year=c.year + 1)).isoformat() }}{% endif %}"
)


def scripts(cfg: dict) -> dict[str, dict]:
    tasks = cfg["tasks"]
    table = {tid: {"name": t["name"], **({"every": t["every"]} if "every" in t else {"season": str(t["season"])})}
             for tid, t in tasks.items()}
    task_field = {
        "name": "Task",
        "description": "Which maintenance job",
        "required": True,
        "selector": {"select": {"options": [{"label": t["name"], "value": tid} for tid, t in tasks.items()]}},
    }
    unknown_task = {
        "if": [{"condition": "template", "value_template": "{{ task not in tasks }}"}],
        "then": [{"stop": "Unknown maintenance task", "error": True}],
    }

    done = {
        "alias": "Record home maintenance",
        "description": (
            "Record that a home maintenance job was done (today unless a date is given). Moves the "
            "job's due date forward by its interval, or to next year's date for seasonal jobs, and "
            "adds it to the Home Maintenance calendar. Use it when someone says they did one, e.g. "
            "'I changed the furnace filter' or 'we blew out the sprinklers on October 12'. "
            f"Each job's next due date is in input_datetime.maint_<task>; a due date of {NOT_SET} "
            "means nobody has recorded that job yet."
        ),
        "icon": "mdi:check-circle-outline",
        "mode": "queued",
        "fields": {
            "task": task_field,
            "date": {"name": "Done on", "description": "Date it was done, if not today", "required": False,
                     "selector": {"date": {}}},
            "note": {"name": "Note", "description": "Optional note for the log, e.g. which filter",
                     "required": False, "selector": {"text": {}}},
        },
        "sequence": [
            {"variables": {"tasks": table}},
            unknown_task,
            {"variables": {
                "t": "{{ tasks[task] }}",
                "done": "{{ (date | string)[:10] if date is defined and date else now().date().isoformat() }}",
                "memo": "{{ note if note is defined and note else '' }}",
            }},
            {"variables": {"next_due": NEXT_DUE}},
            {"action": "input_datetime.set_datetime", "target": {"entity_id": "input_datetime.maint_{{ task }}"},
             "data": {"date": "{{ next_due }}"}},
            {"action": "calendar.create_event", "target": {"entity_id": CALENDAR}, "data": {
                "summary": "✓ {{ t.name }}{{ ' · ' ~ memo if memo else '' }}",
                "description": "{{ memo ~ ' — ' if memo else '' }}next due {{ next_due }}",
                "start_date": "{{ done }}",
                "end_date": "{{ (strptime(done, '%Y-%m-%d').date() + timedelta(days=1)).isoformat() }}",
            }},
        ],
    }

    snooze = {
        "alias": "Snooze home maintenance",
        "description": "Put a home maintenance job off: it becomes due again in the given number of days (default 7).",
        "icon": "mdi:sleep",
        "mode": "queued",
        "fields": {
            "task": task_field,
            "days": {"name": "Days", "description": "How many days from today", "required": False, "default": 7,
                     "selector": {"number": {"min": 1, "max": 90, "unit_of_measurement": "days"}}},
        },
        "sequence": [
            {"variables": {"tasks": table}},
            unknown_task,
            {"action": "input_datetime.set_datetime", "target": {"entity_id": "input_datetime.maint_{{ task }}"},
             "data": {"date": "{{ (now().date() + timedelta(days=(days | default(7)) | int)).isoformat() }}"}},
        ],
    }

    water = cfg["water"]
    labels = {"fc": "FC", "ph": "pH", "ta": "TA", "ch": "CH", "salt": "Salt"}
    reading_fields = {
        rid: {"name": r["name"].replace("Hot tub ", "").capitalize(), "required": False,
              "description": f"Test strip reading{' in ' + r['unit'] if r['unit'] else ''}",
              "selector": {"number": {"min": r["min"], "max": r["max"], "step": r["step"], "mode": "box"}}}
        for rid, r in water.items()
    }
    set_readings = [
        {"if": [{"condition": "template", "value_template": f"{{{{ {rid} is defined and {rid} not in [none, ''] }}}}"}],
         "then": [{"action": "input_number.set_value", "target": {"entity_id": f"input_number.maint_tub_{rid}"},
                   "data": {"value": f"{{{{ {rid} }}}}"}}]}
        for rid in water
    ]
    # "pH 7.6 · FC 3 · ..." from whatever readings are above zero; pH-like readings keep a decimal.
    summary_parts = " ~ ".join(
        f"(('{labels.get(rid, rid)} ' ~ "
        + (f"('%.1f' | format(states('input_number.maint_tub_{rid}') | float(0)))" if water[rid]["step"] < 0.5 else
           f"((states('input_number.maint_tub_{rid}') | float(0) | round(1) | string) | regex_replace('\\\\.0$', ''))")
        + f" ~ ' · ') if states('input_number.maint_tub_{rid}') | float(0) > 0 else '')"
        for rid in water
    )
    log_test = {
        "alias": "Log hot tub water test",
        "description": (
            "Save a hot tub water test. Pass the test strip readings that were given (free chlorine fc, "
            "pH, total alkalinity ta, calcium hardness ch, salt, in ppm); leave out the rest. It stores "
            "them, logs the test on the Home Maintenance calendar and sets the next test a week out."
        ),
        "icon": "mdi:test-tube",
        "mode": "queued",
        "fields": reading_fields,
        "sequence": [
            *set_readings,
            {"variables": {"readings": "{{ (" + summary_parts + ")[:-3] }}"}},
            {"action": "script.maint_done", "data": {"task": "hot_tub_test", "note": "{{ readings }}"}},
        ],
    }

    dose = {
        "alias": "Log hot tub chemicals",
        "description": "Log a chemical added to the hot tub (and how much, if said) on the Home Maintenance calendar.",
        "icon": "mdi:flask-plus-outline",
        "mode": "queued",
        "fields": {
            "chemical": {"name": "Chemical", "required": True,
                         "selector": {"select": {"options": cfg["chemicals"], "custom_value": True}}},
            "amount": {"name": "Amount", "description": "e.g. 2 tablespoons", "required": False,
                       "selector": {"text": {}}},
        },
        "sequence": [
            {"action": "calendar.create_event", "target": {"entity_id": CALENDAR}, "data": {
                "summary": "Hot tub: {{ chemical }}{{ ' · ' ~ amount if amount is defined and amount else '' }}",
                "start_date_time": "{{ now().strftime('%Y-%m-%d %H:%M:%S') }}",
                "end_date_time": "{{ (now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S') }}",
            }},
        ],
    }
    return {"maint_done": done, "maint_snooze": snooze, "maint_log_water_test": log_test, "maint_tub_dose": dose}


# --------------------------------------------------------------------------------- automations
DUE_TODAY = (
    "{% set ns = namespace(l=[]) %}"
    "{% for s in states.input_datetime if s.object_id.startswith('maint_') and s.state == now().date().isoformat() %}"
    "{% set ns.l = ns.l + [{'task': s.object_id[6:], 'name': s.name | replace(' due', '')}] %}"
    "{% endfor %}{{ ns.l }}"
)
DIGEST = (
    "{% set today = now().date() %}{% set ns = namespace(late=[], soon=[]) %}"
    "{% for s in states.input_datetime | sort(attribute='state') if s.object_id.startswith('maint_') and s.state | regex_match('\\\\d{4}-') and s.state > '2001' %}"
    "{% set n = (strptime(s.state, '%Y-%m-%d').date() - today).days %}"
    "{% set name = s.name | replace(' due', '') %}"
    "{% if n < 0 %}{% set ns.late = ns.late + [name ~ ' (' ~ (-n) ~ ' d)'] %}"
    "{% elif n <= 7 %}{% set ns.soon = ns.soon + [name ~ (' today' if n == 0 else ' (' ~ strptime(s.state, '%Y-%m-%d').strftime('%a') ~ ')')] %}{% endif %}"
    "{% endfor %}"
    "{{ (('Overdue: ' ~ ns.late | join(', ') ~ '. ') if ns.late else '') ~ (('This week: ' ~ ns.soon | join(', ') ~ '.') if ns.soon else '') }}"
)


def automations(cfg: dict) -> dict[str, dict]:
    targets = cfg.get("notify") or []
    per_task = [
        {"action": f"notify.{svc}", "data": {
            "title": "Home maintenance",
            "message": "{{ repeat.item.name }} is due today.",
            "data": {"tag": "maint_{{ repeat.item.task }}", "group": "home-maintenance", "actions": [
                {"action": "MAINT_DONE__{{ repeat.item.task }}", "title": "Done"},
                {"action": "MAINT_SNOOZE__{{ repeat.item.task }}", "title": "Snooze a week"},
            ]},
        }}
        for svc in targets
    ]
    digest = [
        {"action": f"notify.{svc}", "data": {"title": "Home maintenance this week", "message": "{{ digest }}",
                                              "data": {"tag": "maint_digest", "group": "home-maintenance"}}}
        for svc in targets
    ]
    reminders = {
        "id": "home_maintenance_reminders",
        "alias": "Home maintenance reminders",
        "description": "Generated by homeassistant/scripts/setup_maintenance.py. A notification for each "
                       "maintenance job due today, and on Saturdays a digest of what is overdue or due this week.",
        "mode": "single",
        "triggers": [{"trigger": "time", "at": cfg.get("reminder_time", "09:00:00")}],
        "conditions": [],
        "actions": [
            {"variables": {"due_today": DUE_TODAY, "digest": DIGEST}},
            {"repeat": {"for_each": "{{ due_today }}", "sequence": per_task}},
            {"if": [{"condition": "template", "value_template": "{{ now().isoweekday() == 6 and digest | length > 0 }}"}],
             "then": digest},
        ],
    }
    buttons = {
        "id": "home_maintenance_reminder_buttons",
        "alias": "Home maintenance reminder buttons",
        "description": "Generated by homeassistant/scripts/setup_maintenance.py. Done / Snooze on a maintenance notification.",
        "mode": "queued",
        "triggers": [{"trigger": "event", "event_type": "mobile_app_notification_action"}],
        "conditions": [{"condition": "template",
                        "value_template": "{{ (trigger.event.data.action | default('')).startswith('MAINT_') }}"}],
        "actions": [
            {"variables": {"kind": "{{ trigger.event.data.action.split('__')[0] }}",
                           "task": "{{ trigger.event.data.action.split('__')[1] }}"}},
            {"choose": [
                {"conditions": [{"condition": "template", "value_template": "{{ kind == 'MAINT_DONE' }}"}],
                 "sequence": [{"action": "script.maint_done", "data": {"task": "{{ task }}"}}]},
                {"conditions": [{"condition": "template", "value_template": "{{ kind == 'MAINT_SNOOZE' }}"}],
                 "sequence": [{"action": "script.maint_snooze", "data": {"task": "{{ task }}", "days": 7}}]},
            ]},
        ],
    }
    return {reminders["id"]: reminders, buttons["id"]: buttons}


def step_scripts_and_automations(cfg: dict) -> None:
    for sid, body in scripts(cfg).items():
        ha_api.post(f"/api/config/script/config/{sid}", body)
        print(f"  script.{sid} ({body['alias']})")
    for aid, body in automations(cfg).items():
        ha_api.post(f"/api/config/automation/config/{aid}", body)
        print(f"  automation: {body['alias']}")
    if not cfg.get("notify"):
        print("  (no notify targets in tasks.yaml: reminders run but send nothing)")


# --------------------------------------------------------------------------------- Assist
def step_assist(cfg: dict) -> None:
    time.sleep(4)  # saving scripts reloads them; registry updates made during the reload are lost
    entities = list(ASSIST_ALIASES)
    entities += [f"input_datetime.maint_{tid}" for tid in cfg["tasks"]]
    entities += [f"input_number.maint_tub_{rid}" for rid in cfg["water"]]
    msgs = [{"type": "config/entity_registry/update", "entity_id": e, "aliases": a} for e, a in ASSIST_ALIASES.items()]
    msgs.append({"type": "homeassistant/expose_entity", "assistants": ["conversation"],
                 "entity_ids": entities, "should_expose": True})
    asyncio.run(ws_call(msgs))
    print(f"  {len(entities)} entities exposed to Assist")


# --------------------------------------------------------------------------------- dashboard
def check_dashboard(cfg: dict) -> None:
    dash = yaml.safe_load(DASHBOARD.read_text())
    listed = set((dash.get("_defs") or {}).get("upkeep_tasks") or [])
    wanted = {f"input_datetime.maint_{tid}" for tid in cfg["tasks"]}
    for e in sorted(wanted - listed):
        print(f"  note: {e} is not in counter.yaml _defs.upkeep_tasks (it won't show in Up next)")
    for e in sorted(listed - wanted):
        print(f"  note: counter.yaml lists {e}, which tasks.yaml no longer has")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prune", action="store_true", help="delete maint_* date helpers not in tasks.yaml")
    args = ap.parse_args()
    cfg = load()
    print(f"{TASKS_FILE.name}: {len(cfg['tasks'])} tasks")
    print("Log calendar"); step_calendar()
    print("Helpers"); step_helpers(cfg, args.prune)
    print("Scripts and reminders"); step_scripts_and_automations(cfg)
    print("Assist"); step_assist(cfg)
    print("Dashboard"); check_dashboard(cfg)


if __name__ == "__main__":
    main()
