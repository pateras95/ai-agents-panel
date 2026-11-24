"""Windows telemetry and Spotify control for the collector (dual-boot counterpart of ubuntu.py).

Needs: psutil, winsdk, pycaw, tzdata (bundled by scripts/build_windows_agent.py)
Optional: LibreHardwareMonitor with its remote web server on 127.0.0.1:8085 for CPU and SSD temperatures.
Every source is optional: a missing one shows as "Μη διαθέσιμο" in the dashboard.
"""

import asyncio
import base64
import json
import subprocess
from threading import Lock
import time
from urllib.request import ProxyHandler, build_opener

from .ubuntu import metric, stamp, temperature

PLAYBACK = {"play": "try_play_async", "pause": "try_pause_async",
            "next": "try_skip_next_async", "previous": "try_skip_previous_async"}
HARDWARE_MONITOR = "http://127.0.0.1:8085/data.json"
sample_lock = Lock()
last_sample = None
last_sample_time = 0.0
art_cache = {"key": None, "uri": None}


def run(*command):
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(command, capture_output=True, text=True, timeout=3, creationflags=flags)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def cpu_ram():
    try:
        import psutil
    except ImportError:
        return metric(None), metric(None)
    memory = psutil.virtual_memory()
    gib = 1024 ** 3
    return (metric(round(psutil.cpu_percent(interval=.16), 1)),
            metric(round(memory.percent, 1), usedGiB=round((memory.total - memory.available) / gib, 1),
                   totalGiB=round(memory.total / gib, 1)))


def gpu_usage():
    output = run("nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits")
    if output:
        try:
            name, usage, degrees = [part.strip() for part in output.splitlines()[0].split(",", 2)]
            return (metric(float(usage), device=name) if usage.isdecimal() else metric(None, device=name),
                    [temperature(name, "GPU", float(degrees))] if degrees.isdecimal() else [])
        except ValueError:
            pass
    return metric(None), []


def parse_hardware_monitor(tree):
    """Map a LibreHardwareMonitor data.json tree to the sensor names the dashboard expects."""
    readings = []

    def number(text):
        try:
            return float(str(text).replace(",", ".").split()[0])
        except (ValueError, IndexError):
            return None

    def walk(node, hardware, kind):
        text = node.get("Text", "")
        image = node.get("ImageURL", "")
        if "cpu" in image:
            hardware, kind = text, "cpu"
        elif "hdd" in image or "nvme" in image or "ssd" in image:
            hardware, kind = text, "storage"
        elif "gpu" in image or "nvidia" in image or "ati" in image:
            kind = "gpu"
        value = node.get("Value", "")
        if not node.get("Children") and "°C" in str(value):
            degrees = number(value)
            if degrees is not None and kind == "cpu" and "package" in text.lower():
                readings.append(temperature(hardware, "Package id 0", degrees))
            elif degrees is not None and kind == "storage" and not any(r["device"] == "nvme" for r in readings):
                readings.append(temperature("nvme", "Composite", degrees))
        for child in node.get("Children", []):
            walk(child, hardware, kind)

    walk(tree, "", "")
    return readings


def hardware_temperatures():
    try:
        with build_opener(ProxyHandler({})).open(HARDWARE_MONITOR, timeout=1.5) as response:
            return parse_hardware_monitor(json.loads(response.read()))
    except (OSError, ValueError):
        return []


def telemetry():
    global last_sample_time, last_sample
    with sample_lock:
        now = time.monotonic()
        if last_sample is None or now - last_sample_time > 3:
            cpu, ram = cpu_ram()
            gpu, thermal = gpu_usage()
            last_sample = {"cpu": cpu, "gpu": gpu, "ram": ram, "temperatures": thermal + hardware_temperatures()}
            last_sample_time = time.monotonic()
        return last_sample


# ---- Spotify through the Windows media session (SMTC)

async def spotify_session():
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    manager = await Manager.request_async()
    for session in manager.get_sessions():
        if "spotify" in session.source_app_user_model_id.lower():
            return session
    return None


async def artwork_of(properties, key):
    if art_cache["key"] == key:
        return art_cache["uri"]
    uri = None
    try:
        from winsdk.windows.storage.streams import Buffer, InputStreamOptions
        if properties.thumbnail is not None:
            stream = await properties.thumbnail.open_read_async()
            size = min(stream.size, 600_000)
            buffer = Buffer(size)
            await stream.read_async(buffer, size, InputStreamOptions.READ_AHEAD)
            data = bytes(memoryview(buffer))
            if data:
                kind = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
                uri = f"data:{kind};base64," + base64.b64encode(data).decode()
    except Exception:  # artwork is optional
        uri = None
    art_cache.update(key=key, uri=uri)
    return uri


def spotify_volume(value=None):
    """Spotify's own volume (0-100) through the Windows audio sessions; sets it when `value` is given."""
    try:
        from pycaw.pycaw import AudioUtilities
        for session in AudioUtilities.GetAllSessions():
            if session.Process and session.Process.name().lower() == "spotify.exe":
                volume = session.SimpleAudioVolume
                if value is not None:
                    volume.SetMasterVolume(value / 100, None)
                return round(volume.GetMasterVolume() * 100)
    except Exception:
        pass
    return None


async def read_spotify():
    session = await spotify_session()
    if session is None:
        return {"state": "closed", "actions": [], "sampledAt": stamp()}
    properties = await session.try_get_media_properties_async()
    info = session.get_playback_info()
    status = {4: "playing", 5: "paused", 3: "stopped"}.get(int(info.playback_status), "stopped")
    controls = info.controls
    actions = [name for name, allowed in (("play", controls.is_play_enabled), ("pause", controls.is_pause_enabled),
                                          ("next", controls.is_next_enabled), ("previous", controls.is_previous_enabled)) if allowed]
    volume = spotify_volume()
    if volume is not None:
        actions.append("volume")
    artwork = await artwork_of(properties, (properties.title, properties.artist))
    return {"state": status, "title": properties.title, "artist": properties.artist, "artwork": artwork,
            "volume": volume, "actions": actions, "sampledAt": stamp()}


def spotify():
    try:
        return asyncio.run(read_spotify())
    except Exception:
        return {"state": "unavailable", "actions": [], "sampledAt": stamp()}


async def do_action(action):
    session = await spotify_session()
    if session is None:
        return False
    return bool(await getattr(session, PLAYBACK[action])())


def spotify_action(payload):
    if not isinstance(payload, dict):
        return False
    action = payload.get("action")
    if not isinstance(action, str) or action not in (*PLAYBACK, "volume"):
        return False
    if action == "volume":
        level = payload.get("value")
        if type(level) not in (int, float) or not 0 <= level <= 100:
            return False
        return spotify_volume(level) is not None
    try:
        return asyncio.run(do_action(action))
    except Exception:
        return False
