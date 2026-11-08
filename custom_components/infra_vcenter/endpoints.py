"""Address parsing shared by setup/reconfiguration; no network operations."""
import ipaddress
import re


def normalize_host(value):
    host = value.strip().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host:
        raise ValueError("Empty host")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,252}", host) or ".." in host:
            raise ValueError("Use an IP address or DNS name without protocol, path or port") from None
        return host.lower()


def parse_hosts(value):
    """Accept semicolon-separated addresses and preserve their first-seen order."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(";")
    elif isinstance(value, list):
        parts = value
    else:
        raise ValueError("Hosts must be a list or a semicolon-separated string")
    result = []
    for part in parts:
        if not isinstance(part, str):
            raise ValueError("Host entries must be strings")
        if not part.strip():
            continue
        host = normalize_host(part)
        if host not in result:
            result.append(host)
    if len(result) > 64:
        raise ValueError("At most 64 hosts per configuration")
    return result


def normalize_vmware_config(config):
    result = dict(config)
    result["host"] = normalize_host(config["host"]) if config.get("host", "").strip() else ""
    result["esx_hosts"] = ";".join(parse_hosts(config.get("esx_hosts", "")))
    if not result["host"] and not result["esx_hosts"]:
        raise ValueError("Provide a vCenter or at least one ESXi address")
    return result
