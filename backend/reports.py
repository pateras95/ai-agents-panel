"""Read the local daily stand-up history."""

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile


REPORT_FIELDS = (
    ("completed", "Ολοκληρώθηκαν"),
    ("next", "Επόμενα βήματα"),
    ("blockers", "Εμπόδια"),
)


def read_reports(directory: Path):
    reports = []
    for path in directory.glob("*.json"):
        try:
            day = date.fromisoformat(path.stem)
            if day.isoformat() != path.stem:
                raise ValueError("expected YYYY-MM-DD.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            sections = []
            for field, label in REPORT_FIELDS:
                items = data.get(field, [])
                if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                    raise ValueError(f"{field} must be a list of strings")
                sections.append((label, items))
            reports.append((day, sections))
        except (OSError, ValueError) as error:
            print(f"Skipping stand-up {path.name}: {error}", file=sys.stderr)
    return sorted(reports, key=lambda report: report[0], reverse=True)


def report_version(directory, day):
    try:
        return sha256((directory / f"{day}.json").read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def save_report(directory, day, sections):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(sections, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            temporary.replace(directory / f"{day}.json")
        finally:
            temporary.unlink(missing_ok=True)
