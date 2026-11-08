"""vCenter or several directly connected ESXi endpoints."""
from copy import deepcopy
import hashlib

from .client import VCenterClient
from .endpoints import normalize_vmware_config, parse_hosts


class EndpointTypeError(ValueError):
    """The endpoint is not of the requested VMware server type."""


class VMwareConnection:
    def __init__(self, config, group_id=None):
        self.config = normalize_vmware_config(config)
        self.group_id = group_id
        self.cache = {}
        self.endpoints = [(host, VCenterClient({**self.config, "host": host, "esx_hosts": ""}))
                          for host in parse_hosts(self.config["esx_hosts"])] if not self.config["host"] else []
        self.vcenter = VCenterClient(self.config) if self.config["host"] else None

    def validate(self):
        if self.vcenter:
            info = self.vcenter.describe()
            if info["api_type"] != "VirtualCenter":
                raise EndpointTypeError("Use the ESXi list for direct host connections")
            if self.config["esx_hosts"]:
                self.vcenter.collect()  # Validate selected hosts, not only credentials.
            return info["identity"], []
        identities = []
        for _, client in self.endpoints:
            info = client.describe()
            if info["api_type"] != "HostAgent":
                raise EndpointTypeError("The ESXi list accepts direct ESXi endpoints only")
            identities.append(info["identity"])
        unique = sorted(set(identities))
        return "esxi-group:" + hashlib.sha256(";".join(unique).encode()).hexdigest()[:24], unique

    @staticmethod
    def scope(snapshot, identity):
        """Scope VMware managed IDs, which are only unique inside one endpoint."""
        result = {}
        prefix = "esxi:" + identity + ":"
        for record in deepcopy(snapshot).values():
            if record["kind"] == "vcenter":
                continue
            original_id = record["id"]
            record["id"] = prefix + original_id
            attrs = record["attributes"]
            attrs.update(source_endpoint=identity, native_resource_id=original_id, connection_mode="direct")
            if attrs.get("host_id"):
                attrs["host_id"] = prefix + attrs["host_id"]
            for field in ("host_ids", "datastore_ids"):
                if field in attrs:
                    attrs[field] = [prefix + item for item in attrs[field]]
            result[f"{record['kind']}:{record['id']}"] = record
        return result

    def collect(self):
        if self.vcenter:
            return self.vcenter.collect()
        result, unavailable, identities = {}, [], set()
        succeeded = 0
        for host, client in self.endpoints:
            try:
                snapshot = client.collect()
                info = next(row for row in snapshot.values() if row["kind"] == "vcenter")
                if info["attributes"].get("api_type") != "HostAgent":
                    raise EndpointTypeError("Direct endpoint is not an ESXi host")
                identity = info["id"]
                if identity in identities:
                    continue  # DNS/IP aliases of the same physical ESXi.
                identities.add(identity)
                rows = self.scope(snapshot, identity)
                self.cache[host] = rows
                result.update(rows)
                succeeded += 1
            except Exception as error:
                unavailable.append({"host": host, "error": type(error).__name__})
                for key, record in deepcopy(self.cache.get(host, {})).items():
                    # A current successful alias wins over stale cached data.
                    if key in result:
                        continue
                    record["available"] = False
                    record["partial"] = True
                    result[key] = record
        if not succeeded:
            raise ConnectionError("No direct ESXi endpoint is reachable")
        hosts = [r for r in result.values() if r["kind"] == "host"]
        vms = [r for r in result.values() if r["kind"] == "vm"]
        datastores = [r for r in result.values() if r["kind"] == "datastore"]
        group = self.group_id or self.validate()[0]
        result["vcenter:" + group] = {"kind": "vcenter", "id": group, "name": "ESXi directs",
            "metrics": {"hosts": (len(hosts), None), "vms": (len(vms), None),
                "vms_on": (sum(r.get("available", True) and r["metrics"]["power_state"][0] == "poweredOn" for r in vms), None),
                "hosts_connected": (sum(r.get("available", True) and r["metrics"]["connection"][0] == "connected" for r in hosts), None),
                "datastores": (len(datastores), None)},
            "attributes": {"api_type": "HostAgentGroup", "unavailable_endpoints": unavailable},
            "partial": bool(unavailable)}
        # Shared storage across direct hosts has endpoint-local IDs. Do not emit
        # a misleading capacity sum without a vCenter-wide datastore identity.
        return result
