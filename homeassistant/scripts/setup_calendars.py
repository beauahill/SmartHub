#!/usr/bin/env python3
"""Create the community calendars the counter dashboard shows, through Home Assistant's config
flow API. Safe to re-run: calendars that already exist (matched by title) are left alone.

    python3 homeassistant/scripts/setup_calendars.py

Remote calendars (built-in "Remote Calendar" integration, refreshed by HA itself):
  Campbell County Events, Rockpile Museum  -- campbellcountywy.gov iCal feeds
  Gillette College                         -- gillettecollege.org events feed
Local calendars (built-in "Local Calendar"), filled by sync_home_games.py:
  Pronghorn Home Games, Gillette Wild Home Games

The shared household Google calendar is not created here: Google needs an OAuth sign-in, done
once in Settings > Devices & services > Add integration > Google Calendar.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha_api  # noqa: E402

COUNTY = "https://www.campbellcountywy.gov/common/modules/iCalendar/iCalendar.aspx?catID={}&feed=calendar"

REMOTE = {
    "Campbell County Events": COUNTY.format(65),
    "Rockpile Museum": COUNTY.format(33),
    "Gillette College": "https://www.gillettecollege.org/calendars/list/?ical=1",
}
LOCAL = ["Pronghorn Home Games", "Gillette Wild Home Games"]


def existing_titles(domain: str) -> set[str]:
    return {e["title"] for e in ha_api.get(f"/api/config/config_entries/entry?domain={domain}")}


def run_flow(handler: str, user_input: dict) -> None:
    flow = ha_api.post("/api/config/config_entries/flow", {"handler": handler})
    result = ha_api.post(f"/api/config/config_entries/flow/{flow['flow_id']}", user_input)
    if result.get("type") != "create_entry":
        sys.exit(f"{handler} flow for {user_input} did not finish: {result}")
    print(f"  created {handler}: {result['title']}")


def main() -> None:
    have = existing_titles("remote_calendar")
    for name, url in REMOTE.items():
        if name in have:
            print(f"  exists  remote_calendar: {name}")
        else:
            run_flow("remote_calendar", {"calendar_name": name, "url": url, "verify_ssl": True})

    have = existing_titles("local_calendar")
    for name in LOCAL:
        if name in have:
            print(f"  exists  local_calendar: {name}")
        else:
            run_flow("local_calendar", {"calendar_name": name})


if __name__ == "__main__":
    main()
