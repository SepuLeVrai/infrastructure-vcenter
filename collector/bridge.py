"""Linux/IPMI → MQTT Discovery bridge; all remote IPMI commands are read-only."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import threading
import time

from providers import IPMIProvider, LinuxProvider, SSHProvider, read_secret

LOG = logging.getLogger("infra_agent")
CLASSES = {"W": "power", "°C": "temperature", "V": "voltage", "A": "current",
           "GiB": "data_size", "Mbit/s": "data_rate", "s": "duration"}


def validate_config(config):
    for field in (config.get("agent_id", ""), *(s.get("id", "") for s in config.get("sources", []))):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", field):
            raise ValueError("Agent/source identifiers must use letters, numbers, _ or -")
    ids = [source["id"] for source in config.get("sources", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("Source identifiers must be unique")
    if not config.get("sources") or any(s.get("type") not in ("linux", "ssh_linux", "ipmi") for s in config["sources"]):
        raise ValueError("At least one linux/ssh_linux/ipmi source is required")
    if not 30 <= config.get("interval", 60) <= 3600:
        raise ValueError("Interval must be 30-3600 seconds")
    if not config.get("mqtt", {}).get("host"):
        raise ValueError("MQTT host is required")
    for source in config["sources"]:
        if source["type"] == "ssh_linux" and not all(source.get(key) for key in ("host", "username", "private_key_file")):
            raise ValueError("SSH host, username and private_key_file are required")
        if source["type"] == "ipmi" and (not source.get("host") or not source.get("username")):
            raise ValueError("IPMI host and username are required")
        if source["type"] == "ipmi" and source.get("privilege", "USER") not in ("USER", "OPERATOR", "ADMINISTRATOR"):
            raise ValueError("Unsupported IPMI privilege level")
        if source["type"] == "ipmi" and source.get("cipher_suite") is not None and source["cipher_suite"] not in (3, 17):
            raise ValueError("This collector accepts cipher suites 3 or 17")


class Bridge:
    def __init__(self, config, client):
        self.config, self.client = config, client
        self.base = "infrastructure/" + config["agent_id"]
        self.birth_topic = config["mqtt"].get("birth_topic", "homeassistant/status")
        self.discovery_prefix = config["mqtt"].get("discovery_prefix", "homeassistant")
        self.stop = threading.Event()
        self.connected = threading.Event()
        self.discovery = {}
        self.attributes_cache = {}
        self.lock = threading.Lock()
        self.active = {}
        self.providers = [(source, provider_for(source))
                          for source in config["sources"]]

    def publish(self, topic, payload, retain=False):
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False) if isinstance(payload, dict) else payload
        return self.client.publish(topic, encoded, qos=1, retain=retain)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            LOG.error("MQTT connection refused (%s)", reason_code)
            return
        self.publish(self.base + "/bridge/availability", "online", True)
        client.subscribe(self.birth_topic, qos=1)
        self.connected.set()
        self.republish_discovery()

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected.clear()

    def on_message(self, client, userdata, message):
        if message.topic == self.birth_topic and message.payload == b"online":
            self.republish_discovery()

    def republish_discovery(self):
        with self.lock:
            configurations = list(self.discovery.items())
            attributes = list(self.attributes_cache.items())
        for topic, payload in configurations:
            self.publish(topic, payload, True)
        for topic, payload in attributes:
            self.publish(topic, payload, True)

    def topics(self, source, key):
        identity = f"{self.config['agent_id']}:{source['id']}:{key}"
        ident = "infra_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
        base = f"{self.base}/{source['id']}"
        return ident, base, self.discovery_prefix + "/sensor/" + ident + "/config"

    def discovery_payload(self, source, key, reading):
        ident, base, topic = self.topics(source, key)
        expiry = max(240, self.config.get("interval", 60)*4)
        template = "{% if (as_timestamp(now()) - (value_json.sample_time | float(0))) | abs <= " + str(expiry) + " %}{{ value_json['values'].get(" + json.dumps(key) + ") }}{% else %}None{% endif %}"
        payload = {"name": reading["label"], "unique_id": ident,
            "state_topic": base + "/state", "value_template": template,
            "json_attributes_topic": base + "/attributes/" + ident,
            "availability": [{"topic": self.base + "/bridge/availability"}, {"topic": base + "/availability"}],
            "availability_mode": "all", "expire_after": expiry,
            "device": {"identifiers": ["infra_agent:" + self.config["agent_id"] + ":" + source["id"]],
                "name": source.get("name", source["id"]), "manufacturer": "Dell" if source["type"] == "ipmi" else "Linux",
                "model": source.get("model", "iDRAC 6" if source["type"] == "ipmi" else "Linux standalone")},
        }
        unit = reading.get("unit")
        if unit:
            payload.update(unit_of_measurement=unit, state_class="measurement")
            if unit in CLASSES:
                payload["device_class"] = CLASSES[unit]
        return topic, payload

    def send(self, source, readings, metadata):
        source = {**source, "name": source.get("name") or metadata.get("hostname") or source["id"]}
        values, current = {}, set()
        for key, reading in readings.items():
            ident, base, topic = self.topics(source, key)
            current.add(topic)
            discovery = self.discovery_payload(source, key, reading)[1]
            with self.lock:
                changed = self.discovery.get(topic) != discovery
                self.discovery[topic] = discovery
            if changed:
                self.publish(topic, discovery, True)
            attrs = {"integration_domain": "infra_agent", "source_id": source["id"],
                "agent_id": self.config["agent_id"], "source_uid": self.config["agent_id"] + ":" + source["id"],
                "source_type": "idrac" if source["type"] == "ipmi" else "standalone",
                "resource_type": "hardware" if source["type"] == "ipmi" else "standalone",
                "resource_id": source["id"], "resource_name": source.get("name", source["id"]),
                "metric_key": key, "metric_name": reading["label"], "metric_role": reading.get("role") or key,
                **metadata}
            attribute_topic = base + "/attributes/" + ident
            with self.lock:
                attributes_changed = self.attributes_cache.get(attribute_topic) != attrs
                self.attributes_cache[attribute_topic] = attrs
            if attributes_changed:
                self.publish(attribute_topic, attrs, True)
            values[key] = reading["value"]
        # Preserve discovery IDs/history if a probe temporarily disappears. The
        # shared state then yields None for that reading instead of retaining it.
        self.active[source["id"]] = self.active.get(source["id"], set()) | current
        self.publish(f"{self.base}/{source['id']}/state", {"values": values, "sample_time": time.time()})
        self.publish(f"{self.base}/{source['id']}/availability", "online", True)

    def run(self):
        while not self.stop.is_set():
            if not self.connected.wait(1):
                continue
            started = time.monotonic()
            for source, provider in self.providers:
                if self.stop.is_set():
                    break
                try:
                    readings, metadata = provider.collect()
                    if self.connected.is_set():
                        self.send(source, readings, metadata)
                except Exception as error:
                    self.publish(f"{self.base}/{source['id']}/availability", "offline", True)
                    LOG.error("Source %s unavailable (%s)", source["id"], getattr(error, "code", type(error).__name__))
            self.stop.wait(max(1, self.config.get("interval", 60) - (time.monotonic()-started)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--once", action="store_true", help="Read providers once and print readings; do not connect to MQTT")
    parser.add_argument("--check", action="store_true", help="Validate configuration without network requests")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    if args.check:
        print("Configuration valid (connectivity and credentials not tested)")
        return
    if args.once:
        for source in config["sources"]:
            provider = provider_for(source)
            readings, metadata = provider.collect()
            print(json.dumps({"source": source["id"], "readings": readings, "metadata": metadata}, ensure_ascii=False))
        return
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="infra_" + config["agent_id"])
    bridge = Bridge(config, client)
    client.on_connect, client.on_disconnect, client.on_message = bridge.on_connect, bridge.on_disconnect, bridge.on_message
    client.on_connect_fail = lambda *_: LOG.error("MQTT connection failed; check broker address, port and routing")
    client.will_set(bridge.base + "/bridge/availability", "offline", qos=1, retain=True)
    connection = config["mqtt"]
    if connection.get("username"):
        client.username_pw_set(connection["username"], read_secret(connection, "password"))
    if connection.get("tls", False):
        client.tls_set(ca_certs=connection.get("ca_file"))
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect_async(connection["host"], connection.get("port", 8883 if connection.get("tls") else 1883), keepalive=30)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: bridge.stop.set())
    client.loop_start()
    try:
        bridge.run()
    finally:
        try:
            if client.is_connected():
                bridge.publish(bridge.base + "/bridge/availability", "offline", True).wait_for_publish(timeout=5)
        finally:
            client.disconnect()
            client.loop_stop()


def provider_for(source):
    return {"linux": LinuxProvider, "ssh_linux": SSHProvider, "ipmi": IPMIProvider}[source["type"]](source)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
