#!/usr/bin/env bash
# Start Claude Code with the NEXUS status line so the dashboard can show its usage limits.
cd "$(dirname "${BASH_SOURCE[0]}")/.." && exec python3 -B -m backend.limits --claude-session
