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

# Current Wi-Fi IPv4 address, empty while Wi-Fi is off or not yet connected.
wifi_address() {
    ip -4 addr show wlan0 2>/dev/null | sed -n 's/^ *inet \([0-9.]*\)\/.*/\1/p' | head -n 1
}

while true; do
    address=$(wifi_address)
    if [ -z "$address" ]; then
        # After a restart or a Wi-Fi drop there is no address to bind to yet.
        if [ "$(settings get global wifi_on 2>/dev/null)" = 0 ]; then
            svc wifi enable >/dev/null 2>&1
        fi
        sleep 5 &
        child=$!
        wait "$child"
        child=
        continue
    fi

    "$directory/bin/python3.13" -B -u "$directory/release/launch.py" --bind "$address" --port 18767 &
    child=$!
    # Follow DHCP changes: restart the server when the Wi-Fi address changes.
    while kill -0 "$child" 2>/dev/null; do
        sleep 5
        if [ "$(wifi_address)" != "$address" ]; then
            kill "$child" 2>/dev/null
            break
        fi
    done
    wait "$child"
    child=
    sleep 3
done
