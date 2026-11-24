#!/usr/bin/env bash
# Build the dashboard and install the current checkout on the USB-connected Lenovo tablet.
# Usage: scripts/deploy_lenovo.sh [--no-build]   (needs npm on PATH unless --no-build)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
directory=$(cat "$HOME/.local/state/nexus-lenovo-pilot/remote")
[[ "$directory" =~ ^/data/local/tmp/nexus-actual\.[A-Za-z0-9]+$ ]] || { echo "Invalid Lenovo runtime directory" >&2; exit 1; }
if [[ "${1:-}" != "--no-build" ]]; then npm --prefix frontend run build; fi
adb -d shell "rm -rf $directory/release/frontend/dist/assets"
adb -d push frontend/dist/. "$directory/release/frontend/dist/" >/dev/null
# Only the backend modules that already exist on the tablet are replaced.
for file in $(adb -d shell "ls $directory/release/backend/" | tr -d '\r' | grep '\.py$'); do
    [[ -f "backend/$file" ]] && adb -d push "backend/$file" "$directory/release/backend/$file" >/dev/null
done
adb -d shell "kill \$(cat $directory/production.pid)"   # the watchdog restarts the server
echo "Deployed to the Lenovo."
