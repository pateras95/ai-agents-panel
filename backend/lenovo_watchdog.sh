#!/system/bin/sh
# This process lives on Android and keeps running after the USB shell exits.
directory=$1
child=
trap 'if [ -n "$child" ]; then kill "$child" 2>/dev/null; wait "$child" 2>/dev/null; fi; exit 0' TERM INT
printf '%s\n' "$$" > "$directory/watchdog.pid"
export NEXUS_DATA_DIR="$directory/production-data"
export NEXUS_COLLECTOR_URL=http://127.0.0.1:18769
export NEXUS_NETWORK_ROUTER=192.168.1.1
export NEXUS_NETWORK_LAN=192.168.1.0/24
export PYTHONTZPATH="$directory/tz"
export PILOT_PID_FILE="$directory/production.pid"

while true; do
    "$directory/bin/python3.13" -B -u "$directory/release/launch.py" --bind 192.168.1.238 --port 18767 &
    child=$!
    wait "$child"
    child=
    sleep 3
done
