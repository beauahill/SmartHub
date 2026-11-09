#!/usr/bin/env python3
"""Fill the two local "home games" calendars in Home Assistant.

    python3 homeassistant/scripts/sync_home_games.py [--dry-run]

Pronghorn Home Games   Gillette College men's and women's basketball, from the college's
                       PrestoSports iCal feeds, keeping only games at the Pronghorn Center.
Gillette Wild Home Games
                       from homeassistant/calendars/gillette_wild_home.yaml.

Events already in the calendar (same start and summary) are skipped, so re-running after the
schedule changes only adds what's new. Run it again at the start of each season; the Pronghorn
feed URL follows the season automatically.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

TZ = ZoneInfo("America/Denver")
WILD_FILE = ha_api.REPO / "homeassistant" / "calendars" / "gillette_wild_home.yaml"
PRESTO = "https://gillette.prestosports.com/sports/{sport}/{season}/schedule?print=ical"
SPORTS = {"mbkb": "Pronghorns MBB", "wbkb": "Pronghorns WBB"}
UA = "Mozilla/5.0 (X11; Linux x86_64) SmartHub-calendar-sync"


def season_slug(today: date) -> str:
    y = today.year if today.month >= 7 else today.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/calendar, */*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_ics(text: str) -> list[dict]:
    """Minimal VEVENT parser: unfolds lines, returns dicts of property -> (params, value)."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    events, cur = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, value = line.split(":", 1)
            name, *params = key.split(";")
            cur[name] = (dict(p.split("=", 1) for p in params if "=" in p), value)
    return events


def ics_datetime(prop) -> tuple[datetime | None, date | None]:
    params, value = prop
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return None, date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ), None
    tz = ZoneInfo(params["TZID"]) if "TZID" in params else TZ
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz).astimezone(TZ), None


def unescape(s: str) -> str:
    return s.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\\\", "\\")


def pronghorn_events(today: date) -> list[dict]:
    out = []
    for sport, label in SPORTS.items():
        url = PRESTO.format(sport=sport, season=season_slug(today))
        try:
            events = parse_ics(fetch(url))
        except Exception as e:  # noqa: BLE001
            print(f"  {label}: could not fetch {url} ({e})")
            continue
        n = 0
        for ev in events:
            location = unescape(ev.get("LOCATION", ({}, ""))[1])
            summary = unescape(ev.get("SUMMARY", ({}, ""))[1])
            if not re.search(r"pronghorn center|gillette,? w", location, re.I):
                continue  # away or neutral site
            if "DTSTART" not in ev:
                continue
            start, day = ics_datetime(ev["DTSTART"])
            if (start.date() if start else day) < today:
                continue
            # "(Men's Basketball) Casper College vs. Gillette College" -> "Pronghorns MBB vs Casper College"
            opponent = re.sub(r"^\([^)]*\)\s*", "", summary)
            opponent = re.sub(r"\s*\(\d+-\d+\)\s*$", "", opponent)
            opponent = re.sub(r"\s*vs\.?\s*Gillette College\s*$", "", opponent, flags=re.I)
            opponent = re.sub(r"^Gillette College\s*vs\.?\s*", "", opponent, flags=re.I)
            out.append(
                {
                    "summary": f"{label} vs {opponent.strip()}",
                    "start": start,
                    "day": day,
                    "minutes": 120,
                    "location": "Pronghorn Center, Gillette College",
                    "description": summary,
                }
            )
            n += 1
        print(f"  {label}: {n} upcoming home games in the {season_slug(today)} feed")
    return out


def wild_events(today: date) -> list[dict]:
    data = yaml.safe_load(WILD_FILE.read_text())
    out = []
    for g in data["games"]:
        d = g["date"] if isinstance(g["date"], date) else date.fromisoformat(str(g["date"]))
        if d < today:
            continue
        h, m = (int(x) for x in str(g["time"]).split(":"))
        out.append(
            {
                "summary": f"Gillette Wild vs {g['opponent']}",
                "start": datetime(d.year, d.month, d.day, h, m, tzinfo=TZ),
                "day": None,
                "minutes": int(data.get("duration_minutes", 150)),
                "location": data.get("venue", "Spirit Hall Ice Arena"),
                "description": f"NA3HL {data.get('season', '')} home game".strip(),
            }
        )
    print(f"  Gillette Wild: {len(out)} upcoming home games in {WILD_FILE.name}")
    return out


def existing(entity_id: str, start: datetime, end: datetime) -> set[tuple[str, str]]:
    items = ha_api.get(f"/api/calendars/{entity_id}?start={start.isoformat()}&end={end.isoformat()}")
    keys = set()
    for it in items:
        s = it["start"].get("dateTime") or it["start"].get("date")
        if "dateTime" in it["start"]:
            s = datetime.fromisoformat(s).astimezone(TZ).isoformat()
        keys.add((it["summary"], s))
    return keys


def sync(entity_id: str, events: list[dict], dry_run: bool) -> None:
    if not events:
        return
    now = datetime.now(TZ)
    have = existing(entity_id, now - timedelta(days=1), now + timedelta(days=400))
    added = skipped = 0
    for ev in events:
        if ev["start"]:
            key = (ev["summary"], ev["start"].isoformat())
            body = {
                "start_date_time": ev["start"].isoformat(),
                "end_date_time": (ev["start"] + timedelta(minutes=ev["minutes"])).isoformat(),
            }
        else:
            key = (ev["summary"], ev["day"].isoformat())
            body = {"start_date": ev["day"].isoformat(), "end_date": (ev["day"] + timedelta(days=1)).isoformat()}
        if key in have:
            skipped += 1
            continue
        body.update(
            {"entity_id": entity_id, "summary": ev["summary"], "location": ev["location"], "description": ev["description"]}
        )
        if dry_run:
            print(f"    would add {key[1][:16]}  {ev['summary']}")
        else:
            ha_api.post("/api/services/calendar/create_event", body)
        added += 1
    print(f"  {entity_id}: {added} added, {skipped} already there")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.now(TZ).date()
    print("Pronghorn basketball")
    sync("calendar.pronghorn_home_games", pronghorn_events(today), args.dry_run)
    print("Gillette Wild hockey")
    sync("calendar.gillette_wild_home_games", wild_events(today), args.dry_run)


if __name__ == "__main__":
    main()
