"""Generate a collector configuration from a list of Linux server addresses."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket


def parse_hosts(raw):
    result = []
    for part in raw.split(";"):
        host = part.strip().rstrip(".")
        if not host:
            continue
        try:
            host = ipaddress.ip_address(host.strip("[]")).compressed
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,252}", host) or ".." in host:
                raise ValueError("Use IP addresses or DNS names without protocol, path or port") from None
            host = host.lower()
        if host not in result:
            result.append(host)
    if len(result) > 64:
        raise ValueError("At most 64 Linux hosts")
    return result


def generate(args):
    sources = [{"id": "local", "type": "linux", "name": socket.gethostname(), "mounts": ["/"]}] if args.local else []
    for host in parse_hosts(args.linux_hosts):
        ident = "linux-" + hashlib.sha256(host.encode()).hexdigest()[:12]
        sources.append({"id": ident, "type": "ssh_linux", "host": host, "username": args.ssh_user,
            "private_key_file": args.ssh_key, "known_hosts_file": args.known_hosts, "mounts": ["/"]})
    if not sources:
        raise ValueError("Select local collection or provide at least one remote Linux address")
    return {"agent_id": args.agent_id, "interval": 60,
        "mqtt": {"host": args.mqtt_host, "port": 1883, "username": args.mqtt_user,
            "password_env": "INFRA_MQTT_PASSWORD", "tls": False}, "sources": sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux-hosts", help="Remote Linux IP/DNS addresses separated by semicolons")
    parser.add_argument("--local", action="store_true", help="Also monitor this collector machine locally")
    parser.add_argument("--mqtt-host")
    parser.add_argument("--mqtt-user", default="infra-monitor")
    parser.add_argument("--agent-id", default="infrastructure")
    parser.add_argument("--ssh-user", default="monitor")
    parser.add_argument("--ssh-key", default="/etc/infra-agent/ssh/id_ed25519")
    parser.add_argument("--known-hosts", default="/etc/infra-agent/ssh/known_hosts")
    parser.add_argument("--output", type=Path, default=Path("config.generated.json"))
    args = parser.parse_args()
    if args.linux_hosts is None:
        args.linux_hosts = input("Remote Linux addresses (separated by ;, empty for none): ")
        args.local = input("Also collect this machine locally? [y/N]: ").strip().lower() in ("y", "yes", "o", "oui")
    if not args.mqtt_host:
        args.mqtt_host = input("MQTT broker IP/DNS: ").strip()
    if args.output.exists():
        raise FileExistsError("Output exists; choose a new --output to preserve its sources and secrets references")
    config = generate(args)
    from bridge import validate_config
    validate_config(config)
    args.output.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created {args.output}. Configure SSH keys/known_hosts and MQTT secrets before starting the service.")


if __name__ == "__main__":
    main()
