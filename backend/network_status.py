"""Run local, targeted reachability checks from the dashboard host."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from ipaddress import IPv4Address, ip_network
import json
import os
from pathlib import Path
import socket
import subprocess
from tempfile import NamedTemporaryFile
from threading import Event, Lock, Thread
from time import monotonic, sleep

from .limits import ATHENS

DEVICE_KINDS = {"generic", "tv", "speaker", "tablet", "computer", "phone"}
PUBLIC_PROBES = ("1.1.1.1", "8.8.8.8")


def now():
    return datetime.now(ATHENS).isoformat(timespec="seconds")


def ping(address):
    try:
        return subprocess.run(["ping", "-c", "1", "-W", "1", address],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=2).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def reachable_neighbors():
    try:
        result = subprocess.run(["ip", "-4", "neigh", "show"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=2, check=True)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {fields[0] for line in result.stdout.splitlines()
            if len(fields := line.split()) >= 3 and fields[-1] == "REACHABLE"
            and "lladdr" in fields}


def tcp(address, port):
    try:
        with socket.create_connection((address, port), timeout=1.5):
            return True
    except OSError:
        return False


def status(available, previous, at):
    return {"available": available, "checkedAt": at,
            "lastSuccess": at if available else previous.get("lastSuccess")}


class NetworkMonitor:
    def __init__(self, directory, local_address, router, lan):
        self.file = Path(directory) / "network-devices.json"
        self.local = str(IPv4Address(local_address))
        self.router = str(IPv4Address(router))
        self.lan = ip_network(lan, strict=False)
        self.lock = Lock()
        self.changed = Event()
        self.devices = {}
        self.last_seen = {}
        self.statuses = {}
        self.gateway = {}
        self.internet = {}
        if self.file.is_file():
            records = json.loads(self.file.read_text(encoding="utf-8"))
            self.devices = {item["ip"]: item for item in records}
        elif IPv4Address(self.local) in self.lan:
            self.devices.setdefault(self.local, {"ip": self.local, "name": "Lenovo", "kind": "tablet"})

    def snapshot(self):
        with self.lock:
            devices = [
                {**entry, "available": self.statuses.get(address),
                 "lastSeen": self.last_seen.get(address), "connection": None}
                for address, entry in self.devices.items()
            ]
            devices.sort(key=lambda item: (item["available"] is not True, item["name"].casefold()))
            return {"source": "known", "router": self.gateway.copy(),
                    "internet": self.internet.copy(), "devices": devices}

    def watch(self):
        while True:
            self.changed.clear()
            self.refresh()
            self.changed.wait(20)

    def refresh(self):
        with self.lock:
            addresses = tuple(self.devices)
        neighbors = reachable_neighbors()
        started = monotonic()
        with ThreadPoolExecutor(max_workers=8) as pool:
            gateway = pool.submit(lambda: ping(self.router) or tcp(self.router, 80))
            internet = [pool.submit(tcp, address, 443) for address in PUBLIC_PROBES]
            devices = {address: pool.submit(ping, address) for address in addresses if address != self.local}
            router_ok = gateway.result()
            internet_ok = any(probe.result() for probe in internet)
            device_states = {address: result.result() for address, result in devices.items()}
        if any(not online and address not in neighbors for address, online in device_states.items()):
            # A stale neighbor can take five seconds to be revalidated by the kernel.
            sleep(max(0, 6 - (monotonic() - started)))
            neighbors.update(reachable_neighbors())
        for address in neighbors.intersection(device_states):
            device_states[address] = True
        if self.local in addresses:
            device_states[self.local] = True
        at = now()
        with self.lock:
            self.statuses = {address: online for address, online in device_states.items()
                             if address in self.devices}
            self.last_seen.update({address: at for address, online in self.statuses.items() if online})
            self.gateway = {**status(router_ok, self.gateway, at), "address": self.router}
            self.internet = status(internet_ok, self.internet, at)

    def save(self, payload):
        address = IPv4Address(payload["ip"])
        name = payload["name"].strip()
        kind = payload["kind"]
        if (not name or len(name) > 60 or any(ord(char) < 32 for char in name)
                or kind not in DEVICE_KINDS or address not in self.lan
                or address in (self.lan.network_address, self.lan.broadcast_address)
                or str(address) == self.router):
            raise ValueError("Invalid device")
        address = str(address)
        with self.lock:
            if address not in self.devices and len(self.devices) >= 32:
                raise ValueError("Maximum known devices reached")
            records = {**self.devices, address: {"ip": address, "name": name, "kind": kind}}
            self.persist(records)
        self.changed.set()
        return records[address]

    def delete(self, ip):
        address = str(IPv4Address(ip))
        with self.lock:
            records = self.devices.copy()
            records.pop(address, None)
            self.persist(records)
            self.statuses.pop(address, None)
            self.last_seen.pop(address, None)

    def persist(self, records):
        self.file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.file.parent, delete=False) as output:
            temporary = Path(output.name)
            try:
                json.dump(list(records.values()), output, ensure_ascii=False)
                output.flush()
                temporary.replace(self.file)
            finally:
                temporary.unlink(missing_ok=True)
        self.devices = records


def configured_monitor(directory, bind):
    router = os.environ.get("NEXUS_NETWORK_ROUTER")
    if not router:
        return None
    monitor = NetworkMonitor(directory, bind, router, os.environ.get("NEXUS_NETWORK_LAN", "192.168.1.0/24"))
    Thread(target=monitor.watch, name="network-monitor", daemon=True).start()
    return monitor
