"""Read Ubuntu telemetry and expose the allowlisted Spotify MPRIS operations."""

from datetime import datetime
import math
from pathlib import Path
import subprocess
from threading import Lock
import time
from urllib.parse import urlsplit

from .limits import ATHENS


PLAYER = ["playerctl", "-p", "spotify"]
MPRIS = ["busctl", "--user", "get-property", "org.mpris.MediaPlayer2.spotify",
         "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"]
PLAYBACK = {"play": "CanPlay", "pause": "CanPause", "next": "CanGoNext", "previous": "CanGoPrevious"}
sample_lock = Lock()
last_sample = None
last_sample_time = 0.0


def run(*command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def stamp():
    return datetime.now(ATHENS).isoformat(timespec="seconds")


def metric(value, unit="%", **extra):
    return {"value": value, "unit": unit, "sampledAt": stamp() if value is not None else None, **extra}


def cpu_ticks():
    fields = Path("/proc/stat").read_text().splitlines()[0].split()
    values = [int(field) for field in fields[1:9]]
    return sum(values), values[3] + values[4]


def cpu_usage():
    try:
        total, idle = cpu_ticks()
        time.sleep(.16)
        end_total, end_idle = cpu_ticks()
        return metric(round(100 * (1 - (end_idle - idle) / (end_total - total)), 1))
    except (OSError, ValueError, ZeroDivisionError, IndexError):
        return metric(None)


def ram_usage():
    try:
        fields = {key.strip(): int(value.split()[0])
                  for key, value in (line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())}
        total = fields["MemTotal"]
        used = total - fields["MemAvailable"]
        return metric(round(100 * used / total, 1), usedGiB=round(used / 1048576, 1),
                      totalGiB=round(total / 1048576, 1))
    except (OSError, ValueError, KeyError, ZeroDivisionError):
        return metric(None)


def temperature(device, sensor, value):
    return {"device": device, "sensor": sensor, **metric(value, "°C")}


def thermal_sensors():
    readings = []
    for device in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        for path in sorted(device.glob("temp*_input")):
            try:
                name = (device / "name").read_text().strip()
                sensor = path.stem.removesuffix("_input")
                label = device / f"{sensor}_label"
                if label.is_file():
                    sensor = label.read_text().strip()
                readings.append(temperature(name, sensor, round(float(path.read_text()) / 1000, 1)))
            except (OSError, ValueError):
                continue
    return readings


def gpu_usage():
    output = run("nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits")
    if output:
        try:
            name, usage, degrees = [part.strip() for part in output.splitlines()[0].split(",", 2)]
            return (metric(float(usage), device=name) if usage.isdecimal() else metric(None, device=name),
                    [temperature(name, "GPU", float(degrees))] if degrees.isdecimal() else [])
        except ValueError:
            pass
    for path in sorted(Path("/sys/class/drm").glob("card*/device/gpu_busy_percent")):
        try:
            return metric(float(path.read_text()), device=path.parent.parent.name), []
        except (OSError, ValueError):
            continue
    return metric(None), []


def telemetry():
    global last_sample_time, last_sample
    with sample_lock:
        now = time.monotonic()
        if last_sample is None or now - last_sample_time > 3:
            gpu, thermal = gpu_usage()
            last_sample = {
                "cpu": cpu_usage(), "gpu": gpu, "ram": ram_usage(),
                "temperatures": thermal + thermal_sensors(),
            }
            last_sample_time = time.monotonic()
        return last_sample


def player_property(name):
    return run(*MPRIS, name)


def spotify():
    status = run(*PLAYER, "status")
    if status is None:
        listed = run("playerctl", "-l") or ""
        return {"state": "unavailable" if "spotify" in listed.splitlines() else "closed",
                "actions": [], "sampledAt": stamp()}
    metadata = run(*PLAYER, "metadata", "--format", "{{title}}\n{{artist}}\n{{mpris:artUrl}}") or ""
    title, artist, artwork = (metadata.split("\n") + ["", "", ""])[:3]
    try:
        image = urlsplit(artwork)
        artwork = artwork if image.scheme == "https" and image.netloc == "i.scdn.co" else None
    except ValueError:
        artwork = None
    try:
        volume = float(run(*PLAYER, "volume") or "nan")
        volume = round(volume * 100) if math.isfinite(volume) and 0 <= volume <= 1 else None
    except ValueError:
        volume = None
    control = player_property("CanControl") == "b true"
    actions = [action for action, prop in PLAYBACK.items() if control and player_property(prop) == "b true"]
    if control and volume is not None:
        actions.append("volume")
    return {"state": status.lower(), "title": title, "artist": artist, "artwork": artwork,
            "volume": volume, "actions": actions, "sampledAt": stamp()}


def spotify_action(payload):
    if not isinstance(payload, dict):
        return False
    action = payload.get("action")
    if not isinstance(action, str) or action not in (*PLAYBACK, "volume"):
        return False
    if player_property("CanControl") != "b true":
        return False
    if action == "volume":
        level = payload.get("value")
        if type(level) not in (int, float) or not 0 <= level <= 100:
            return False
        if run(*PLAYER, "volume") is None:
            return False
        return run(*PLAYER, "volume", str(level / 100)) is not None
    if player_property(PLAYBACK[action]) != "b true":
        return False
    return run(*PLAYER, action) is not None
