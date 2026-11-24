#!/usr/bin/env python3
"""Build the self-contained Windows agent zip (embedded Python, libraries, backend code, start scripts).

Run on Ubuntu with internet access. The result is outside Git and is installed on the tablet by
scripts/deploy_lenovo.sh (or copy it to <tablet data dir>/windows-agent/nexus-windows-agent.zip).
"""

import argparse
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path.home() / ".local/share/nexus-ai/windows-agent/nexus-windows-agent.zip"
PYTHON = "3.12.8"
LIBRARIES = ["psutil", "winsdk", "pycaw", "comtypes", "tzdata"]
BACKEND = ["__init__.py", "windows_agent.py", "windows_system.py", "ubuntu.py", "limits.py"]

START = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "NEXUS AI agent" /min "%~dp0python\pythonw.exe" -B -m backend.windows_agent
echo Το NEXUS AI agent ξεκίνησε. Μπορείς να κλείσεις αυτό το παράθυρο.
"""
START_VISIBLE = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0python\python.exe" -B -m backend.windows_agent
pause
"""
AUTOSTART_ON = r"""@echo off
chcp 65001 >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v NexusAIAgent /t REG_SZ /d "\"%~dp0start.bat\"" /f
echo Το agent θα ξεκινά αυτόματα όταν συνδέεσαι στα Windows.
pause
"""
AUTOSTART_OFF = r"""@echo off
chcp 65001 >nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v NexusAIAgent /f
echo Η αυτόματη εκκίνηση αφαιρέθηκε.
pause
"""
README = """NEXUS AI agent για Windows
==========================

1. Αποσυμπίεσε αυτόν τον φάκελο κάπου μόνιμα (π.χ. C:\\NexusAI).
2. Διπλό κλικ στο start.bat. Δεν χρειάζεται Python, pip ή άλλη εγκατάσταση.
3. Στο tablet επίλεξε "Windows". Το Σύστημα και τα Εργαλεία συνδέονται μέσα σε λίγα δευτερόλεπτα.

Αυτόματη εκκίνηση: διπλό κλικ στο autostart-on.bat (autostart-off.bat για να φύγει).
Αν κάτι δεν δουλεύει, τρέξε το start-visible.bat για να δεις μηνύματα.

Εργαλεία (κουμπιά): ανοίγουν μόνο όσα γράφονται στο launcher.json (δημιουργείται στην πρώτη εκκίνηση).
Μπορείς να προσθέσεις δικά σου. Κάθε στοιχείο έχει "id", "label", "icon" και είτε
  "open": ένα αρχείο, φάκελος ή σύνδεσμος (π.χ. "steam://open/main"), είτε
  "run": λίστα με πρόγραμμα και ορίσματα (π.χ. ["C:\\\\Program Files\\\\App\\\\app.exe"]).
Το tablet στέλνει μόνο το id, ποτέ διαδρομή ή εντολή.

Το config.json περιέχει τον ιδιωτικό κωδικό σύνδεσης με το tablet. Μην το μοιράζεσαι.
"""


def download_wheel(name, python_tag, directory):
    """Download the newest Windows x64 wheel of a PyPI project that fits the embedded Python (no pip needed)."""
    import json
    directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as response:
        data = json.load(response)
    releases = sorted(data["releases"].items(), key=lambda item: [int(p) if p.isdigit() else 0 for p in item[0].replace("b", ".").replace("rc", ".").split(".")], reverse=True)
    for version, files in releases:
        for file in files:
            tags = file["filename"][:-4].split("-")
            if file["packagetype"] != "bdist_wheel" or file.get("yanked"):
                continue
            python, abi, platform = tags[-3:]
            if platform in ("win_amd64", "any") and python in (python_tag, "py3", "py2.py3", "cp3") or (
                    platform == "win_amd64" and abi == "abi3" and python.startswith("cp3")):
                fetch(file["url"], directory / file["filename"])
                return
    raise SystemExit(f"No Windows wheel found for {name} ({python_tag})")


def fetch(url, target):
    print("Downloading", url)
    urllib.request.urlretrieve(url, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    major_minor = "".join(PYTHON.split(".")[:2])
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        package = work / "nexus-windows-agent"
        python = package / "python"
        python.mkdir(parents=True)
        embed = work / "embed.zip"
        fetch(f"https://www.python.org/ftp/python/{PYTHON}/python-{PYTHON}-embed-amd64.zip", embed)
        with zipfile.ZipFile(embed) as archive:
            archive.extractall(python)
        wheels = work / "wheels"
        for name in LIBRARIES:
            download_wheel(name, f"cp{major_minor}", wheels)
        site = python / "Lib" / "site-packages"
        site.mkdir(parents=True)
        for wheel in wheels.glob("*.whl"):
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(site)
        # With a ._pth file Python ignores the script directory and PYTHONPATH: list every path explicitly.
        (python / f"python{major_minor}._pth").write_text(
            f"python{major_minor}.zip\n.\nLib\\site-packages\n..\nimport site\n")
        backend = package / "backend"
        backend.mkdir()
        for name in BACKEND:
            shutil.copy(ROOT / "backend" / name, backend / name)
        for name, text in (("start.bat", START), ("start-visible.bat", START_VISIBLE), ("autostart-on.bat", AUTOSTART_ON),
                           ("autostart-off.bat", AUTOSTART_OFF), ("README.txt", README)):
            (package / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8-sig" if name == "README.txt" else "utf-8"))
        args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(work))
    print("Wrote", args.output, round(args.output.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
