"""Run local, targeted reachability checks from the dashboard host."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from ipaddress import IPv4Address, ip_network
import json
import os
from pathlib import Path
import re
import socket
import subprocess
from tempfile import NamedTemporaryFile
from threading import Event, Lock, Thread
from time import monotonic, sleep, time

from .limits import ATHENS

DEVICE_KINDS = {"generic", "tv", "speaker", "tablet", "computer", "phone",
                "router", "camera", "vacuum", "printer", "console", "iot"}
# Order matters: the first matching hint wins. Used only as an estimate from the device name.
KIND_HINTS = (
    ("camera", r"cam(era)?\b|ipc\b|webcam|doorbell|cctv|kamera|κάμερα"),
    ("vacuum", r"vacuum|robot|roborock|rockrobo|roomba|dreame|σκούπα"),
    ("router", r"router|gateway|modem|access ?point|\bap\b"),
    ("phone", r"iphone|android|galaxy|pixel|redmi|oneplus|phone|mobile|huawei|τηλέφωνο"),
    ("tablet", r"ipad|tablet|\btab\b"),
    ("tv", r"\btv\b|bravia|roku|chromecast|fire ?tv|smart ?tv|webos|tizen|shield|τηλεόραση"),
    ("speaker", r"sonos|echo|homepod|speaker|soundbar|nest mini|alexa|ηχείο"),
    ("computer", r"macbook|imac|laptop|desktop|\bpc\b|ubuntu|windows|linux|workstation|υπολογιστής"),
    ("printer", r"printer|epson|canon|brother|laserjet|εκτυπωτής"),
    ("console", r"playstation|ps[45]\b|xbox|nintendo|switch"),
)


def guess_kind(name):
    lowered = name.casefold()
    for kind, pattern in KIND_HINTS:
        if re.search(pattern, lowered):
            return kind
    return None
PUBLIC_PROBES = ("1.1.1.1", "8.8.8.8")
MAC = re.compile(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}")
SWEEP_SECONDS = 90
FORGET_SECONDS = 30 * 24 * 3600


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


def neighbor_table():
    """{ip: mac} for neighbors the kernel has a link-layer address for."""
    try:
        result = subprocess.run(["ip", "-4", "neigh", "show"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=3, check=True)
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if "lladdr" in fields and fields[-1] not in ("FAILED", "INCOMPLETE"):
            mac = fields[fields.index("lladdr") + 1].lower()
            if MAC.fullmatch(mac):
                table[fields[0]] = mac
    return table


def dns_name(data, offset):
    """Read a possibly compressed DNS name; return its labels and the offset just after it."""
    labels, end, jumps = [], None, 0
    while True:
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if end is None:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumps += 1
            if jumps > 8:
                raise ValueError("compression loop")
        elif length == 0:
            return labels, (end if end is not None else offset + 1)
        else:
            labels.append(data[offset + 1:offset + 1 + length].decode("utf-8", "replace"))
            offset += length + 1


def mdns_name(address, port=5353):
    """Ask the device itself for its name: a unicast mDNS reverse lookup (PTR)."""
    reverse = ".".join(reversed(address.split("."))) + ".in-addr.arpa"
    question = b"".join(bytes([len(part)]) + part.encode() for part in reverse.split(".")) + b"\x00\x00\x0c\x00\x01"
    packet = b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00" + question
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.8)
            sock.sendto(packet, (address, port))
            data = sock.recv(1500)
        questions, answers = int.from_bytes(data[4:6], "big"), int.from_bytes(data[6:8], "big")
        offset = 12
        for _ in range(questions):
            offset = dns_name(data, offset)[1] + 4
        for _ in range(answers):
            _, offset = dns_name(data, offset)
            kind = int.from_bytes(data[offset:offset + 2], "big")
            length = int.from_bytes(data[offset + 8:offset + 10], "big")
            offset += 10
            if kind == 12:
                labels = dns_name(data, offset)[0]
                name = labels[0] if labels else ""
                return name.replace("-", " ") if name and name != address else ""
            offset += length
    except (OSError, IndexError, ValueError, UnicodeError):
        pass
    return ""


def hostname(address):
    try:
        name = socket.gethostbyaddr(address)[0].split(".")[0]
    except (OSError, UnicodeError):
        name = ""
    return name if name and name != address else mdns_name(address)


def private_mac(mac):
    """Phones randomize their MAC per network; the locally administered bit is set then."""
    return bool(int(mac[:2], 16) & 2)


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
        self.found_file = Path(directory) / "network-discovered.json"
        self.found = {}
        self.last_sweep = 0.0
        if self.found_file.is_file():
            try:
                self.found = {item["mac"]: item for item in json.loads(self.found_file.read_text(encoding="utf-8"))
                              if MAC.fullmatch(item["mac"])}
            except (OSError, ValueError, KeyError, TypeError):
                self.found = {}
        if self.file.is_file():
            records = json.loads(self.file.read_text(encoding="utf-8"))
            self.devices = {item["ip"]: item for item in records}
        elif IPv4Address(self.local) in self.lan:
            self.devices.setdefault(self.local, {"ip": self.local, "name": "Lenovo", "kind": "tablet"})

    def snapshot(self):
        with self.lock:
            by_mac = {entry["mac"]: entry for entry in self.found.values()}
            known_macs = {entry["mac"] for entry in self.devices.values() if entry.get("mac")}
            devices = []
            for address, entry in self.devices.items():
                found = by_mac.get(entry.get("mac"))
                guessed = guess_kind(entry["name"]) if entry["kind"] == "generic" else None
                entry = {**entry, "kind": guessed or entry["kind"], "guessed": guessed is not None}
                if found:
                    devices.append({**entry, "ip": found["ip"], "available": found["online"],
                                    "lastSeen": found["lastSeen"], "connection": None, "discovered": False})
                else:
                    devices.append({**entry, "available": self.statuses.get(address),
                                    "lastSeen": self.last_seen.get(address), "connection": None, "discovered": False})
            known_ips = {item["ip"] for item in devices}
            for found in self.found.values():
                if found["mac"] in known_macs or found["ip"] in known_ips:
                    continue
                kind = guess_kind(found.get("hostname") or "") or ("phone" if private_mac(found["mac"]) else "generic")
                devices.append({
                    "ip": found["ip"], "mac": found["mac"], "kind": kind, "guessed": kind != "generic",
                    "name": found.get("hostname") or ("Ιδιωτική συσκευή" if private_mac(found["mac"]) else "Άγνωστη συσκευή")
                            + " ." + found["ip"].rsplit(".", 1)[1],
                    "available": found["online"], "lastSeen": found["lastSeen"], "connection": None, "discovered": True,
                })
            taken = {item["ip"] for item in devices}
            if self.local not in taken:
                devices.append({"ip": self.local, "kind": "tablet", "name": "Αυτό το tablet", "available": True,
                                "lastSeen": now(), "connection": None, "discovered": False, "fixed": True})
            if self.router not in taken:
                devices.append({"ip": self.router, "kind": "router", "name": "Router", "available": self.gateway.get("available"),
                                "lastSeen": self.gateway.get("lastSuccess"), "connection": None, "discovered": False,
                                "fixed": True})
            devices.sort(key=lambda item: (item["available"] is not True, item["name"].casefold()))
            return {"source": "discovered", "router": self.gateway.copy(),
                    "internet": self.internet.copy(), "devices": devices}

    def sweep(self):
        """Ping every address of the local network once so the kernel learns who is there, then read the neighbors."""
        hosts = [str(host) for host in self.lan.hosts()][:510]
        with ThreadPoolExecutor(max_workers=48) as pool:
            answered = {host for host, ok in zip(hosts, pool.map(ping, hosts)) if ok}
        table = neighbor_table()
        with self.lock:
            known = {entry["ip"] for entry in self.found.values() if entry.get("hostname") is not None}
        names = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            lookups = {ip: pool.submit(hostname, ip) for ip in table if ip not in known and ip in answered}
            for ip, job in lookups.items():
                try:
                    names[ip] = job.result(timeout=3)
                except Exception:
                    names[ip] = ""
        at = now()
        stamp = monotonic()
        with self.lock:
            for entry in self.found.values():
                entry["online"] = False
            for ip, mac in table.items():
                if ip == self.router or ip == self.local or IPv4Address(ip) not in self.lan:
                    continue
                entry = self.found.setdefault(mac, {"mac": mac, "ip": ip, "hostname": ""})
                entry["ip"] = ip
                entry["online"] = ip in answered
                if entry["online"]:
                    entry["lastSeen"] = at
                    entry["seenAt"] = time()
                if names.get(ip):
                    entry["hostname"] = names[ip]
                entry.setdefault("lastSeen", None)
                entry.setdefault("seenAt", time())
            for mac in [mac for mac, entry in self.found.items()
                        if time() - entry.get("seenAt", 0) > FORGET_SECONDS]:
                del self.found[mac]
            records = list(self.found.values())
            self.link_known()
        self.last_sweep = stamp
        try:
            self.found_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.found_file.parent, delete=False) as output:
                temporary = Path(output.name)
                try:
                    json.dump([{key: value for key, value in item.items() if key != "online"} for item in records],
                              output, ensure_ascii=False)
                    output.flush()
                    temporary.replace(self.found_file)
                finally:
                    temporary.unlink(missing_ok=True)
        except OSError:
            pass

    def link_known(self):
        """A device named by IP keeps its name when its address changes: remember its MAC the first time it is seen."""
        by_ip = {entry["ip"]: entry for entry in self.found.values()}
        changed = False
        records = {}
        for address, entry in self.devices.items():
            found = by_ip.get(address)
            if found and not entry.get("mac"):
                entry = {**entry, "mac": found["mac"]}
                changed = True
            records[address] = entry
        if changed:
            try:
                self.persist(records)
            except OSError:
                pass

    def watch(self):
        while True:
            self.changed.clear()
            self.refresh()
            self.changed.wait(20)

    def refresh(self):
        if monotonic() - self.last_sweep > SWEEP_SECONDS:
            self.sweep()
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
        mac = payload.get("mac")
        if mac is not None and (not isinstance(mac, str) or not MAC.fullmatch(mac.lower())):
            raise ValueError("Invalid device")
        with self.lock:
            if address not in self.devices and len(self.devices) >= 32:
                raise ValueError("Maximum known devices reached")
            mac = mac.lower() if mac else self.devices.get(address, {}).get("mac")
            record = {"ip": address, "name": name, "kind": kind, **({"mac": mac} if mac else {})}
            records = {key: value for key, value in self.devices.items() if not mac or value.get("mac") != mac}
            records[address] = record
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
