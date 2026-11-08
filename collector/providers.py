"""Read-only Linux and iDRAC6/IPMI providers. No MQTT or HA dependency."""
import csv
import hashlib
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import socket
import time


def stable_key(label):
    readable = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:48] or "sensor"
    return readable + "_" + hashlib.sha256(label.encode()).hexdigest()[:8]


def label_role(label, category):
    text = re.sub(r"system board\s*\d*", "", label.lower())
    if category == "temperature" and re.search(r"ambient|inlet|ambiant|entrée", text):
        return "temperature:ambient"
    return category + ":" + re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def metric(value, unit, label, role=None):
    return {"value": value, "unit": unit, "label": label, "role": role}


def read_secret(config, name):
    """Credentials belong in environment variables or mounted secret files."""
    if config.get(name + "_file"):
        return Path(config[name + "_file"]).read_text(encoding="utf-8").rstrip("\r\n")
    variable = config.get(name + "_env")
    if not variable or variable not in os.environ:
        raise ValueError(f"Missing {name} secret")
    return os.environ[variable]


def parse_ipmi_sensors(output):
    readings = {}
    health = []
    units = {"degrees c": ("°C", "temperature"), "rpm": ("rpm", "fan"),
             "watts": ("W", "component_power"), "volts": ("V", "voltage"),
             "amps": ("A", "current")}
    aggregate = []
    for row in csv.reader(io.StringIO(output)):
        if len(row) < 4:
            continue
        label, raw, unit, status = [part.strip() for part in row[:4]]
        if not label:
            continue
        ident = stable_key(label)
        status = status.lower()
        if status in ("ok", "nc", "cr", "nr"):
            state = "green" if status == "ok" else "yellow" if status == "nc" else "red"
            readings[f"hardware:{ident}:health"] = metric(state, None, label + " · Santé", label_role(label, "health"))
            health.append(state)
        if unit.lower() not in units:
            if unit.lower() == "discrete" and (raw.lower() not in ("na", "n/a", "") or status not in ("ns", "na", "")):
                readings[f"hardware:{ident}:state"] = metric(f"{raw} · {status}", None, label + " · État brut", label_role(label, "state"))
            continue
        native_unit, category = units[unit.lower()]
        try:
            number = float(raw)
            if not math.isfinite(number):
                continue
        except ValueError:
            continue
        if category != "temperature" and number < 0:
            continue
        # Missing sensors are absent, never a fabricated zero.
        readings[f"hardware:{ident}"] = metric(number, native_unit, label, label_role(label, category))
        # Explicit whole-system readings only; never sum PSU/component watts.
        if category == "component_power" and re.search(r"^system level$|system.*(?:power|pwr)|(?:power|pwr).*consumption|total.*power", label, re.I):
            if not re.search(r"capacity|maximum|rated|budget|limit", label, re.I):
                aggregate.append((f"hardware:{ident}", number))
    if len(aggregate) == 1:
        ident, number = aggregate[0]
        readings.pop(ident, None)
        readings["power_w"] = metric(number, "W", "Puissance serveur", "power_w")
    if health:
        readings["hardware_health"] = metric("red" if "red" in health else "yellow" if "yellow" in health else "green", None, "Santé capteurs IPMI", "hardware_health")
    return readings


def parse_dcmi_power(output):
    if re.search(r"power reading state is:\s*deactivated", output, re.I):
        return None
    match = re.search(r"Instantaneous power reading:\s*(\d+)\s*Watts", output, re.I)
    return float(match[1]) if match else None


class IPMIError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class IPMIProvider:
    def __init__(self, config):
        self.config = config

    def command(self, args, csv_output=False):
        env = os.environ.copy()
        env["IPMI_PASSWORD"] = read_secret(self.config, "password")
        env["LC_ALL"] = "C"
        # USER privilege suffices on many firmwares; it can be set to OPERATOR
        # when explicitly required by a firmware. No write commands are issued.
        command = ["ipmitool", "-I", "lanplus", "-H", self.config["host"],
                   "-U", self.config["username"], "-E", "-L", self.config.get("privilege", "USER"),
                   "-N", "3", "-R", "1"]
        if self.config.get("cipher_suite") is not None:
            command.extend(["-C", str(self.config["cipher_suite"])])
        if csv_output:
            command.append("-c")
        result = subprocess.run(command + list(args), env=env, capture_output=True,
                                text=True, timeout=35, check=False)
        if result.returncode:
            # ipmitool errors may echo user-supplied fields. Do not log them.
            message = ((result.stderr or "") + (result.stdout or "")).lower()
            code = "ipmi_privilege" if "privilege" in message else "ipmi_auth" if any(
                part in message for part in ("password", "unauthorized", "rakp 2 hmac", "invalid user")) else "ipmi_timeout" if any(
                part in message for part in ("timed out", "timeout")) else "ipmi_session_or_command"
            raise IPMIError(code)
        return result.stdout

    def collect(self):
        readings = parse_ipmi_sensors(self.command(["sensor"], csv_output=True))
        if not readings:
            raise RuntimeError("No supported IPMI sensors")
        try:
            watts = parse_dcmi_power(self.command(["dcmi", "power", "reading"]))
            if watts is not None:
                readings["power_w"] = metric(watts, "W", "Puissance serveur", "power_w")
                power_method = "dcmi"
            else:
                power_method = "sdr" if "power_w" in readings else "unavailable"
        except (RuntimeError, subprocess.TimeoutExpired):
            power_method = "sdr" if "power_w" in readings else "unavailable"
        try:
            power = self.command(["chassis", "power", "status"])
            match = re.search(r"Chassis Power is (on|off)", power, re.I)
            if match:
                readings["power_state"] = metric("poweredOn" if match[1].lower() == "on" else "poweredOff", None, "Alimentation", "power_state")
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        return readings, {"power_method": power_method, "model": self.config.get("model", "iDRAC 6")}


class LinuxProvider:
    def __init__(self, config):
        self.config = config
        self.previous_cpu = None
        self.previous_network = None

    def collect(self):
        readings = {"connection": metric("connected", None, "Connexion"),
                    "uptime": metric(float(Path("/proc/uptime").read_text().split()[0]), "s", "Uptime")}
        # The first interval is unknown; counters need two observations.
        fields = [int(v) for v in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
        cpu = (sum(fields), fields[3] + fields[4])
        cpu_used = None
        if self.previous_cpu:
            total, idle = cpu[0] - self.previous_cpu[0], cpu[1] - self.previous_cpu[1]
            if total > 0 and idle >= 0:
                cpu_used = round(max(0, min(100, (total - idle) / total * 100)), 2)
        self.previous_cpu = cpu
        readings["cpu_used"] = metric(cpu_used, "%", "CPU")
        memory = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw = line.split(":", 1)
            memory[key] = int(raw.split()[0]) * 1024
        total = memory["MemTotal"]
        available = memory.get("MemAvailable")
        used = total - available if available is not None else None
        readings.update({"ram_total": metric(round(total/1024**3, 3), "GiB", "RAM totale"),
                         "ram_used": metric(round(used/1024**3, 3) if used is not None else None, "GiB", "RAM utilisée"),
                         "ram_percent": metric(round(used/total*100, 2) if used is not None and total else None, "%", "RAM")})
        mounts = self.config.get("mounts", ["/"])
        for mount in mounts:
            try:
                disk = shutil.disk_usage(mount)
                readings[f"filesystem:{mount}:used"] = metric(round(disk.used/disk.total*100, 2) if disk.total else None, "%", f"{mount} · Occupation")
                readings[f"filesystem:{mount}:free"] = metric(round(disk.free/1024**3, 3), "GiB", f"{mount} · Libre")
            except OSError:
                continue
        now, network, nics = time.monotonic(), {}, []
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            name, rest = line.split(":", 1)
            name = name.strip()
            if name == "lo" or (self.config.get("interfaces") and name not in self.config["interfaces"]):
                continue
            if not self.config.get("interfaces") and Path(f"/sys/devices/virtual/net/{name}").exists():
                continue
            numbers = rest.split()
            network[name] = (int(numbers[0]), int(numbers[8]))
            try:
                speed = int(Path(f"/sys/class/net/{name}/speed").read_text())
            except (OSError, ValueError):
                speed = None
            nics.append({"device": name, "key": name, "speed_mbps": speed if speed and speed > 0 else None})
            for index, direction in enumerate(("rx", "tx")):
                rate = None
                if self.previous_network and name in self.previous_network[1]:
                    elapsed = now - self.previous_network[0]
                    delta = network[name][index] - self.previous_network[1][name][index]
                    if elapsed > 0 and delta >= 0:
                        rate = round(delta*8/elapsed/1_000_000, 4)
                readings[f"net_{direction}:{name}"] = metric(rate, "Mbit/s", f"{name} · {'Réception' if direction == 'rx' else 'Émission'}")
        self.previous_network = now, network
        try:
            sensors = subprocess.run(["sensors", "-j"], capture_output=True, text=True, timeout=10, check=True)
            for chip, features in json.loads(sensors.stdout).items():
                if not isinstance(features, dict):
                    continue
                for label, values in features.items():
                    if not isinstance(values, dict):
                        continue
                    for key, number in values.items():
                        if not key.endswith("_input") or not isinstance(number, (int, float)):
                            continue
                        category = "temperature" if key.startswith("temp") else "fan" if key.startswith("fan") else "component_power" if key.startswith("power") else None
                        if not category:
                            continue
                        unit = {"temperature": "°C", "fan": "rpm", "component_power": "W"}[category]
                        name = f"{chip} · {label}"
                        readings[f"hardware:{stable_key(name + key)}"] = metric(number, unit, name, label_role(name, category))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        # CPU/package watts from lm-sensors are not whole-system consumption.
        return readings, {"model": "Linux", "hostname": socket.gethostname(), "physical_nics": nics, "network_collection": "ok"}


class SSHProvider:
    """Read Linux metrics through an authenticated one-shot Python process."""
    def __init__(self, config):
        self.config = config

    def collect(self):
        host = self.config["host"]
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,252}", host) or ".." in host:
                raise ValueError("Invalid SSH host") from None
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*\$?", self.config["username"]):
            raise ValueError("Invalid SSH username")
        known_hosts = self.config.get("known_hosts_file", "/etc/infra-agent/ssh/known_hosts")
        command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", "ConnectTimeout=10", "-o", f"UserKnownHostsFile={known_hosts}",
                   "-i", self.config["private_key_file"], "-p", str(self.config.get("port", 22)),
                   "-l", self.config["username"], host, "python3", "-"]
        remote_config = {key: self.config[key] for key in ("mounts", "interfaces") if key in self.config}
        # Only read code and JSON data are sent. No agent file, daemon or package
        # is installed on the remote server. Two observations produce rates.
        program = Path(__file__).read_text(encoding="utf-8") + "\n" + (
            "provider = LinuxProvider(json.loads(" + repr(json.dumps(remote_config)) + "))\n"
            "provider.collect()\ntime.sleep(1)\n"
            "readings, metadata = provider.collect()\n"
            "print(json.dumps({'readings': readings, 'metadata': metadata}))\n")
        result = subprocess.run(command, input=program, capture_output=True, text=True, timeout=75, check=False)
        if result.returncode:
            text = (result.stderr or "").lower()
            error = RuntimeError("SSH collection failed")
            error.code = "ssh_host_key" if "host key verification failed" in text else "ssh_auth" if "permission denied" in text else "ssh_connection_or_python"
            raise error
        for line in reversed(result.stdout.splitlines()):
            try:
                data = json.loads(line)
                if isinstance(data, dict) and isinstance(data.get("readings"), dict) and isinstance(data.get("metadata"), dict):
                    return data["readings"], {**data["metadata"], "collection_transport": "ssh"}
            except ValueError:
                continue
        raise ValueError("Remote Python did not return a valid metrics object")
