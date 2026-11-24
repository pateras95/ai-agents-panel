"""Pick the telemetry and Spotify implementation of the system the collector runs on."""

import os

if os.name == "nt":
    from .windows_system import spotify, spotify_action, telemetry
else:
    from .ubuntu import spotify, spotify_action, telemetry

OS_NAME = "windows" if os.name == "nt" else "linux"
