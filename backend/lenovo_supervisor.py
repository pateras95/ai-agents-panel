"""Bootstrap the Lenovo watchdog and restore the optional USB collector link."""

from pathlib import Path
import re
from shlex import quote
import subprocess
import time

from .lenovo_address import ADB as ADB_PATH


ADB = [ADB_PATH, "-d"]
STATE = Path.home() / ".local/state/nexus-lenovo-pilot/remote"
TUNNEL = "tcp:18769"


def adb(*arguments):
    try:
        result = subprocess.run(ADB + list(arguments), capture_output=True, text=True, timeout=6)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def runtime_directory():
    """The runtime directory on the tablet: remembered in a local file, otherwise found over ADB (e.g. on a fresh Windows)."""
    try:
        return STATE.read_text().strip()
    except OSError:
        found = adb("shell", "ls -d /data/local/tmp/nexus-actual.*") or ""
        directory = found.splitlines()[0].strip() if found else ""
        if directory:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(directory)
        return directory


def main():
    directory = runtime_directory()
    if not re.fullmatch(r"/data/local/tmp/nexus-actual\.[A-Za-z0-9]+", directory):
        raise SystemExit("Invalid Lenovo runtime directory")
    path = f"{directory}/release/lenovo_watchdog.sh"
    ensure = f"""
        pid=$(cat {quote(directory + "/watchdog.pid")} 2>/dev/null)
        if test -n "$pid" &&
            tr '\\000' '\\n' </proc/"$pid"/cmdline 2>/dev/null | grep -Fxq {quote(path)}; then
            exit 0
        fi
        toybox nohup toybox setsid /system/bin/sh {quote(path)} {quote(directory)} \
          </dev/null >>{quote(directory + "/watchdog.log")} 2>&1 &
        echo started
    """
    while True:
        ready = adb("shell", "test \"$(getprop sys.boot_completed)\" = 1 && "
                    "test \"$(getprop ro.product.model)\" = 'Lenovo TB-X606F' && "
                    f"test -f {quote(path)} && echo ready")
        if ready == "ready":
            links = adb("reverse", "--list")
            if not links or not any(line.split()[-2:] == [TUNNEL, TUNNEL] for line in links.splitlines()):
                adb("reverse", TUNNEL, TUNNEL)
            if adb("shell", "-T", ensure) == "started":
                print("Started the Lenovo-local watchdog", flush=True)
        time.sleep(8)


if __name__ == "__main__":
    main()
