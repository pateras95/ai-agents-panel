#!/usr/bin/env python3
"""Show the Claude Code and Codex subscription windows on Ubuntu."""

import argparse
import asyncio
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
from zoneinfo import ZoneInfo


UNAVAILABLE = "Μη διαθέσιμο"
ATHENS = ZoneInfo("Europe/Athens")
WINDOWS = (("5ωρο", "five_hour", 300), ("7 ημέρες", "seven_day", 10080))
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "nexus-ai" / "claude-limits.json"


def mapping(value):
    return value if isinstance(value, dict) else {}


def timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, ATHENS) if value > 0 else None
    except (OverflowError, OSError, ValueError):
        return None


def used_percent(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if 0 <= value <= 100 and math.isfinite(value) else None


def claude_windows():
    try:
        with CACHE.open(encoding="utf-8") as source:
            return mapping(json.load(source)), os.fstat(source.fileno()).st_mtime
    except (OSError, ValueError):
        return {}, None


def capture_claude():
    payload = mapping(json.load(sys.stdin))
    incoming = mapping(payload.get("rate_limits"))
    windows = {}
    for _, key, _ in WINDOWS:
        window = mapping(incoming.get(key))
        if window:
            reset = window.get("resets_at")
            windows[key] = {
                "used_percentage": used_percent(window.get("used_percentage")),
                "resets_at": reset if timestamp(reset) is not None else None,
            }

    CACHE.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=CACHE.parent, delete=False
    ) as output:
        temporary_path = Path(output.name)
        try:
            json.dump(windows, output)
            output.flush()
            temporary_path.replace(CACHE)
        finally:
            temporary_path.unlink(missing_ok=True)


def start_claude_session():
    capture_command = shlex.join([
        sys.executable, str(Path(__file__).resolve()), "--capture-claude"
    ])
    settings = json.dumps({"statusLine": {"type": "command", "command": capture_command}})
    os.execvp("claude", ["claude", "--settings", settings])


async def read_codex():
    process = await asyncio.create_subprocess_exec(
        "codex", "app-server", "--listen", "stdio://",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()

    async def response(request_id):
        while line := await process.stdout.readline():
            message = mapping(json.loads(line))
            if message.get("id") == request_id:
                if "error" in message:
                    raise ValueError("Το Codex App Server επέστρεψε σφάλμα.")
                return mapping(message.get("result"))
        raise ValueError("Το Codex App Server έκλεισε πριν απαντήσει.")

    try:
        async with asyncio.timeout(12):
            await send({
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": {"name": "nexus_ai", "version": "0.1.0"}},
            })
            await response(1)
            await send({"method": "initialized"})
            await send({"id": 2, "method": "account/rateLimits/read"})
            result = await response(2)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()

    buckets = mapping(result.get("rateLimitsByLimitId"))
    bucket = mapping(buckets.get("codex"))
    if not bucket:
        fallback = mapping(result.get("rateLimits"))
        if fallback.get("limitId") in (None, "codex"):
            bucket = fallback
    windows = {}
    for key in ("primary", "secondary"):
        window = mapping(bucket.get(key))
        duration = window.get("windowDurationMins")
        if type(duration) is int:
            windows[duration] = window
    return windows


def format_window(used, resets_at):
    percent = used_percent(used)
    reset = timestamp(resets_at)
    if reset is not None and reset.timestamp() <= time.time():
        return UNAVAILABLE, UNAVAILABLE
    remaining = UNAVAILABLE if percent is None else f"{100 - percent:g}%"
    reset_text = UNAVAILABLE if reset is None else reset.strftime("%d/%m/%Y %H:%M %Z")
    return remaining, reset_text


def limit_samples():
    claude, claude_updated = claude_windows()
    codex_updated = None
    try:
        codex = asyncio.run(read_codex())
        codex_updated = time.time()
    except (OSError, TimeoutError, ValueError):
        codex = {}

    for tool, windows, percent_key, reset_key, sampled_at in (
        ("Claude Code", claude, "used_percentage", "resets_at", claude_updated),
        ("Codex", codex, "usedPercent", "resetsAt", codex_updated),
    ):
        for label, claude_key, minutes in WINDOWS:
            key = claude_key if tool == "Claude Code" else minutes
            window = mapping(windows.get(key))
            remaining, reset = format_window(window.get(percent_key), window.get(reset_key))
            updated = timestamp(sampled_at) if remaining != UNAVAILABLE or reset != UNAVAILABLE else None
            yield {
                "tool": tool,
                "window": label,
                "remaining": remaining,
                "reset": reset,
                "updated": updated.strftime("%d/%m/%Y %H:%M %Z") if updated else UNAVAILABLE,
            }


def limit_rows():
    for sample in limit_samples():
        yield sample["tool"], sample["window"], sample["remaining"], sample["reset"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--claude-session", action="store_true",
                         help="Start Claude Code with a temporary status line that captures usage.")
    actions.add_argument("--capture-claude", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.capture_claude:
        capture_claude()
        return
    if args.claude_session:
        start_claude_session()
        return

    print(f"{'Εργαλείο':<13} {'Παράθυρο':<10} {'Υπόλοιπο':<14} Επαναφορά (Europe/Athens)")
    for tool, label, remaining, reset in limit_rows():
        print(f"{tool:<13} {label:<10} {remaining:<14} {reset}")


if __name__ == "__main__":
    main()
