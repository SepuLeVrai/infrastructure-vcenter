"""Synchronous vSphere 6.7 SOAP collector; always called in an executor.

One bounded session per refresh; inventory is retrieved in bulk with the
PropertyCollector. No power, configuration or guest operations are issued.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import ipaddress
import ssl

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl


class AuthenticationError(Exception):
    """Credentials were rejected."""


class HostSelectionError(ValueError):
    """An explicitly selected ESXi was not found in the vCenter inventory."""


def value(obj, path, default=None):
    for part in path.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return default
    return obj


def ratio(used, total):
    return round(used / total * 100, 2) if used is not None and total else None


def mib_to_gib(number):
    return round(number / 1024, 3) if number is not None and number >= 0 else None


def bytes_to_gib(number):
    return round(number / 1024**3, 3) if number is not None and number >= 0 else None


def dns_names(config):
    """Return configured host/FQDN without doing a resolver lookup."""
    host = (value(config, "hostName", "") or "").strip().rstrip(".")
    domain = (value(config, "domainName", "") or "").strip().rstrip(".")
    if not host:
        return None, None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host, host if "." in host or not domain else f"{host}.{domain}"
    return None, None


def numeric_sensor(sensor):
    """Only publish explicit supported units; never guess unspecified readings."""
    units = {"degrees C": "°C", "degrees c": "°C", "celsius": "°C",
             "rpm": "rpm", "watts": "W", "volts": "V", "amps": "A"}
    unit = units.get(sensor.baseUnits)
    if unit is None or value(sensor, "rateUnits", "none") not in ("none", "", None):
        return None
    return round(sensor.currentReading * 10 ** sensor.unitModifier, 3), unit


class VCenterClient:
    def __init__(self, config):
        self.config = config

    @contextmanager
    def session(self):
        context = ssl.create_default_context()
        if not self.config.get("verify_ssl", True):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        service = None
        try:
            service = SmartConnect(
                host=self.config["host"], port=self.config.get("port", 443),
                user=self.config["username"], pwd=self.config["password"],
                sslContext=context, httpConnectionTimeout=20,
            )
            yield service.RetrieveContent()
        except vim.fault.InvalidLogin as err:
            raise AuthenticationError from err
        finally:
            if service is not None:
                try:
                    Disconnect(service)
                except Exception:
                    pass

    def validate(self):
        return self.describe()["identity"]

    def describe(self):
        with self.session() as content:
            api_type = value(content.about, "apiType", "VirtualCenter")
            identity = value(content.about, "instanceUuid")
            if api_type == "HostAgent":
                hosts = self.inventory(content, vim.HostSystem, ["summary"])
                identity = next((value(props.get("summary"), "hardware.uuid") for _, props, _ in hosts
                                 if value(props.get("summary"), "hardware.uuid")), None)
            if not identity:
                raise RuntimeError("The VMware endpoint did not expose a stable identity")
            return {"identity": identity, "api_type": api_type}

    def inventory(self, content, kind, paths):
        view = content.viewManager.CreateContainerView(content.rootFolder, [kind], True)
        try:
            pc = vmodl.query.PropertyCollector
            spec = pc.FilterSpec(
                objectSet=[pc.ObjectSpec(obj=view, skip=True, selectSet=[pc.TraversalSpec(
                    name="view", type=vim.view.ContainerView, path="view", skip=False)])],
                propSet=[pc.PropertySpec(type=kind, all=False, pathSet=paths)],
            )
            page = content.propertyCollector.RetrievePropertiesEx(
                specSet=[spec], options=pc.RetrieveOptions(maxObjects=250))
            result = []
            while page:
                for item in page.objects:
                    props = {prop.name: prop.val for prop in item.propSet}
                    result.append((item.obj._moId, props, bool(item.missingSet)))
                if not page.token:
                    break
                page = content.propertyCollector.ContinueRetrievePropertiesEx(token=page.token)
            return result
        finally:
            view.Destroy()

    def collect(self):
        result = {}

        def add(kind, ident, props, metrics, attributes=None, partial=False):
            result[f"{kind}:{ident}"] = {
                "kind": kind, "id": ident, "name": props.get("name", ident),
                "metrics": metrics, "attributes": attributes or {}, "partial": partial,
            }

        with self.session() as content:
            for ident, p, partial in self.inventory(content, vim.VirtualMachine, [
                "name", "summary", "runtime", "guest", "snapshot", "datastore",
            ]):
                summary, runtime, guest = p.get("summary"), p.get("runtime"), p.get("guest")
                quick, cfg = value(summary, "quickStats"), value(summary, "config")
                powered = str(value(runtime, "powerState", "unknown"))
                running = powered == "poweredOn"
                metrics = {
                    "power_state": (powered, None),
                    "health": (str(value(summary, "overallStatus", "unknown")), None),
                    "cpu_mhz": (value(quick, "overallCpuUsage") if running else None, "MHz"),
                    "vcpu": (value(cfg, "numCpu"), None),
                    "ram_configured": (mib_to_gib(value(cfg, "memorySizeMB")), "GiB"),
                    "ram_active": (mib_to_gib(value(quick, "guestMemoryUsage")) if running else None, "GiB"),
                    "ram_host": (mib_to_gib(value(quick, "hostMemoryUsage")) if running else None, "GiB"),
                    "uptime": (value(quick, "uptimeSeconds") if running else None, "s"),
                    "storage_committed": (bytes_to_gib(value(summary, "storage.committed")), "GiB"),
                    "storage_uncommitted": (bytes_to_gib(value(summary, "storage.uncommitted")), "GiB"),
                    "tools": (value(guest, "toolsRunningStatus"), None),
                }
                snapshot = p.get("snapshot")
                roots = value(snapshot, "rootSnapshotList", [])
                stack, count = list(roots), 0
                while stack:
                    snap = stack.pop()
                    count += 1
                    stack.extend(snap.childSnapshotList)
                metrics["snapshots"] = (count if not partial else None, None)
                disks = []
                for disk in value(guest, "disk", []):
                    disks.append({"path": disk.diskPath, "capacity": disk.capacity, "free": disk.freeSpace})
                    # Guest Tools readings may be stale when the VM is off.
                    prefix = f"filesystem:{disk.diskPath}"
                    metrics[prefix + ":used"] = (ratio(disk.capacity - disk.freeSpace, disk.capacity) if running else None, "%")
                    metrics[prefix + ":free"] = (bytes_to_gib(disk.freeSpace) if running else None, "GiB")
                add("vm", ident, p, metrics, {
                    "host_id": value(runtime, "host._moId"), "ip_address": value(guest, "ipAddress"),
                    "guest_os": value(cfg, "guestFullName"), "filesystems": disks,
                    "instance_uuid": value(cfg, "instanceUuid"),
                    "datastore_ids": [ds._moId for ds in p.get("datastore", [])],
                }, partial)

            for ident, p, partial in self.inventory(content, vim.HostSystem, [
                "name", "summary", "runtime.connectionState", "runtime.inMaintenanceMode",
                "runtime.healthSystemRuntime.systemHealthInfo.numericSensorInfo",
                "config.network.pnic", "config.network.vswitch", "config.network.dnsConfig", "config.network.vnic",
            ]):
                summary = p.get("summary")
                hardware, quick = value(summary, "hardware"), value(summary, "quickStats")
                connected = str(p.get("runtime.connectionState", "unknown")) == "connected"
                cpu_total = value(hardware, "cpuMhz", 0) * value(hardware, "numCpuCores", 0)
                ram_total = value(hardware, "memorySize")
                cpu_used, ram_used = value(quick, "overallCpuUsage"), value(quick, "overallMemoryUsage")
                metrics = {
                    "connection": (str(p.get("runtime.connectionState", "unknown")), None),
                    "maintenance": (("on" if p["runtime.inMaintenanceMode"] else "off") if "runtime.inMaintenanceMode" in p else None, None),
                    "health": (str(value(summary, "overallStatus", "unknown")), None),
                    "cpu_used": (ratio(cpu_used, cpu_total) if connected else None, "%"),
                    "cpu_mhz": (cpu_used if connected else None, "MHz"),
                    "ram_used": (mib_to_gib(ram_used) if connected else None, "GiB"),
                    "ram_total": (bytes_to_gib(ram_total), "GiB"),
                    "ram_percent": (ratio(ram_used * 1024**2 if ram_used is not None else None, ram_total) if connected else None, "%"),
                    "uptime": (value(quick, "uptime") if connected else None, "s"),
                }
                metric_labels = {}
                for sensor in p.get("runtime.healthSystemRuntime.systemHealthInfo.numericSensorInfo", []):
                    key = f"hardware:{value(sensor, 'id') or sensor.name}"
                    metric_labels[key] = sensor.name
                    metric_labels[key + ":health"] = sensor.name + " · Santé"
                    reading = numeric_sensor(sensor)
                    if reading:
                        metrics[key] = (reading[0] if connected else None, reading[1])
                    metrics[key + ":health"] = (value(sensor, "healthState.key"), None)
                dns_hostname, dns_name = dns_names(p.get("config.network.dnsConfig"))
                add("host", ident, p, metrics, {
                    "vendor": value(hardware, "vendor"), "model": value(hardware, "model"),
                    "esxi_version": value(summary, "config.product.version"),
                    "esxi_build": value(summary, "config.product.build"),
                    "dns_hostname": dns_hostname, "dns_name": dns_name,
                    "hardware_uuid": value(hardware, "uuid"),
                    "management_ips": [value(nic, "spec.ip.ipAddress") for nic in p.get("config.network.vnic", [])
                                       if value(nic, "spec.ip.ipAddress")],
                    "metric_labels": metric_labels,
                    "physical_nics": [{"device": nic.device, "key": nic.key,
                        "speed_mbps": value(nic, "linkSpeed.speedMb"),
                        "full_duplex": value(nic, "linkSpeed.duplex"),
                        "mac": value(nic, "mac")} for nic in p.get("config.network.pnic", [])],
                    "vswitches": [{"name": switch.name, "uplink_keys": list(value(switch, "pnic", [])),
                        "mtu": value(switch, "mtu")} for switch in p.get("config.network.vswitch", [])],
                }, partial)

            for ident, p, partial in self.inventory(content, vim.Datastore, ["name", "summary", "host"]):
                summary = p.get("summary")
                capacity, free = value(summary, "capacity"), value(summary, "freeSpace")
                accessible = value(summary, "accessible", False)
                add("datastore", ident, p, {
                    "accessible": ("on" if accessible else "off", None),
                    "capacity": (bytes_to_gib(capacity), "GiB"),
                    "free": (bytes_to_gib(free) if accessible else None, "GiB"),
                    "used": (ratio(capacity - free, capacity) if accessible and capacity is not None and free is not None else None, "%"),
                }, {"type": value(summary, "type"), "host_ids": [
                    mount.key._moId for mount in p.get("host", [])
                ]}, partial)

            requested = [host.strip().lower() for host in self.config.get("esx_hosts", "").split(";") if host.strip()]
            if requested:
                selected = set()
                for host in requested:
                    matches = [r["id"] for r in result.values() if r["kind"] == "host" and host in {
                        str(item).lower() for item in [r["name"], r["attributes"].get("dns_hostname"),
                            r["attributes"].get("dns_name"), *r["attributes"].get("management_ips", [])] if item}]
                    if not matches:
                        raise HostSelectionError("An ESXi selection did not match the vCenter inventory")
                    selected.update(matches)
                result = {key: r for key, r in result.items() if
                    (r["kind"] == "host" and r["id"] in selected) or
                    (r["kind"] == "vm" and r["attributes"].get("host_id") in selected) or
                    (r["kind"] == "datastore" and selected.intersection(r["attributes"].get("host_ids", [])))}
                for record in result.values():
                    if record["kind"] == "datastore":
                        record["attributes"]["host_ids"] = [h for h in record["attributes"]["host_ids"] if h in selected]

            hosts = {r["id"]: r for r in result.values() if r["kind"] == "host"}
            vms = [r for r in result.values() if r["kind"] == "vm"]
            stores = [r for r in result.values() if r["kind"] == "datastore"]
            for record in vms:
                record["attributes"]["host_name"] = hosts.get(record["attributes"].get("host_id"), {}).get("name")
            for record in stores:
                record["attributes"]["host_names"] = [hosts[h]["name"] for h in record["attributes"]["host_ids"] if h in hosts]
            for host_id, host in hosts.items():
                attached = [vm for vm in vms if vm["attributes"].get("host_id") == host_id]
                host["metrics"]["vms"] = (len(attached), None)
                host["metrics"]["vms_on"] = (sum(vm["metrics"]["power_state"][0] == "poweredOn" for vm in attached), None)
                host["metrics"]["datastores"] = (sum(host_id in ds["attributes"]["host_ids"] for ds in stores), None)

            self.collect_network(content, result)

            def storage_total(metric):
                readings = [ds["metrics"][metric][0] for ds in stores]
                return round(sum(readings), 3) if readings and all(v is not None for v in readings) else None

            api_type = value(content.about, "apiType", "VirtualCenter")
            identity = (next((r["attributes"].get("hardware_uuid") for r in hosts.values()
                             if r["attributes"].get("hardware_uuid")), None) if api_type == "HostAgent"
                        else value(content.about, "instanceUuid"))
            if not identity:
                raise RuntimeError("The VMware endpoint did not expose a stable identity")
            add("vcenter", identity, {"name": "vCenter" if api_type == "VirtualCenter" else "ESXi"}, {
                "vms": (sum(r["kind"] == "vm" for r in result.values()), None),
                "hosts": (sum(r["kind"] == "host" for r in result.values()), None),
                "datastores": (sum(r["kind"] == "datastore" for r in result.values()), None),
                "vms_on": (sum(vm["metrics"]["power_state"][0] == "poweredOn" for vm in vms), None),
                "hosts_connected": (sum(h["metrics"]["connection"][0] == "connected" for h in hosts.values()), None),
                "storage_capacity": (storage_total("capacity"), "GiB"),
                "storage_free": (storage_total("free"), "GiB"),
            }, {"version": content.about.version, "build": content.about.build,
                "api_version": content.about.apiVersion, "instance_uuid": identity, "api_type": api_type,
                "scope": "selected_hosts" if requested else "all"})
        return result

    def collect_network(self, content, result):
        """Read real-time network counters; missing/denied stats stay unknown.

        vSphere counters are KiB/s (kiloBytesPerSecond); HA displays decimal
        Mbit/s. Host physical NIC instances are separate from VM aggregate traffic.
        Standard vSwitch topology is inventory only: summing uplinks would not
        account for intra-host VM traffic, so no synthetic vSwitch usage is emitted.
        """
        manager = value(content, "perfManager")
        resources = [r for r in result.values() if r["kind"] in ("host", "vm")]
        for record in resources:
            record["attributes"]["network_collection"] = "no_samples"
        if manager is None:
            return
        try:
            counters = {}
            for counter in manager.perfCounter:
                if (value(counter, "groupInfo.key") == "net" and
                    str(counter.rollupType) == "average" and
                    value(counter, "unitInfo.key") == "kiloBytesPerSecond" and
                    value(counter, "nameInfo.key") in ("received", "transmitted")):
                    counters[counter.key] = "rx" if counter.nameInfo.key == "received" else "tx"
            if not counters:
                return
            specifications = []
            by_id = {}
            for record in resources:
                running = (record["metrics"].get("connection", (None,))[0] == "connected" if record["kind"] == "host"
                           else record["metrics"].get("power_state", (None,))[0] == "poweredOn")
                if not running:
                    record["attributes"]["network_collection"] = "offline"
                    continue
                kind = vim.HostSystem if record["kind"] == "host" else vim.VirtualMachine
                reference = kind(record["id"], content.rootFolder._stub)
                by_id[record["id"]] = record
                specifications.append(vim.PerformanceManager.QuerySpec(
                    entity=reference, intervalId=20, maxSample=1,
                    metricId=[vim.PerformanceManager.MetricId(counterId=ident,
                        instance="*" if record["kind"] == "host" else "") for ident in counters],
                ))
            for start in range(0, len(specifications), 50):
                try:
                    samples = manager.QueryPerf(querySpec=specifications[start:start + 50])
                except Exception as err:
                    for spec in specifications[start:start + 50]:
                        by_id[spec.entity._moId]["attributes"]["network_collection"] = type(err).__name__
                    continue
                for sample in samples:
                    record = by_id.get(sample.entity._moId)
                    if record is None or not sample.sampleInfo:
                        continue
                    timestamp = sample.sampleInfo[-1].timestamp
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    if abs((datetime.now(timezone.utc) - timestamp).total_seconds()) > 180:
                        record["attributes"]["network_collection"] = "stale"
                        continue
                    for series in sample.value:
                        direction = counters.get(series.id.counterId)
                        instance = series.id.instance
                        if not direction or not series.value:
                            continue
                        if record["kind"] == "host" and not instance.startswith("vmnic"):
                            continue
                        suffix = f":{instance}" if instance else ""
                        reading = series.value[-1]
                        record["metrics"][f"net_{direction}{suffix}"] = (
                            round(reading * 1024 * 8 / 1_000_000, 4) if reading >= 0 else None, "Mbit/s")
                        record["attributes"]["network_collection"] = "ok"
                        record["attributes"]["network_sample_time"] = timestamp.isoformat()
        except Exception as err:
            # Network inventory/permission errors must not discard working CPU/RAM.
            for record in resources:
                record["attributes"]["network_collection"] = type(err).__name__
