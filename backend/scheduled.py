"""Collect the most recent completed workday on Ubuntu."""

from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path

from .activity import collect_draft
from .limits import ATHENS
from .reports import save_report


DRAFTS = Path(os.environ.get("NEXUS_DRAFTS_DIR") or Path.home() / ".local/share/nexus-ai/drafts")
WORKDAY_END = time(18)


def latest_workday(now):
    day = now.date()
    if now.time() < WORKDAY_END:
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def available_days():
    return sorted((path.stem for path in DRAFTS.glob("????-??-??.json") if path.is_file()), reverse=True)


def read_draft(day):
    return json.loads((DRAFTS / f"{day.isoformat()}.json").read_text(encoding="utf-8"))


def main():
    now = datetime.now(ATHENS)
    day = latest_workday(now)
    root = Path(__file__).resolve().parents[1]
    draft = collect_draft(day, root, True)
    draft["generatedAt"] = datetime.now(ATHENS).isoformat(timespec="seconds")
    if len(draft["unavailable"]) and not draft["projects"]:
        raise SystemExit("The approved Git repositories were unavailable.")
    DRAFTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    save_report(DRAFTS, day, draft)
    print(f"{day}: {len(draft['projects'])} project(s), {len(draft['unavailable'])} unavailable")


if __name__ == "__main__":
    main()
