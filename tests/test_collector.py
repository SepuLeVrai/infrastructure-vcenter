"""Offline tests for parsers, Linux rates, safe IPMI reads and MQTT discovery."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collector"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".dev-deps"))
import providers
from bridge import Bridge, validate_config


SENSORS = """Ambient Temp,23.000,degrees C,ok
Fan 1,4200.000,RPM,ok
PS1 Input Power,110.000,Watts,ok
PS2 Input Power,90.000,Watts,ok
System Level,200.000,Watts,ok
PS1 Capacity,750.000,Watts,ok
PS1 Status,na,discrete,cr
Unavailable Temp,na,degrees C,ns
"""


class FakeMQTT:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, **options):
        self.messages.append((topic, payload, options))


def config():
    return {"agent_id":"test", "mqtt":{"host":"broker"}, "interval":60,
            "sources":[{"id":"r610", "type":"ipmi", "host":"idrac", "username":"reader", "password_env":"TEST_SECRET", "cipher_suite":3}]}


class CollectorTests(unittest.TestCase):
    def test_sdr_whole_server_power_not_psu_sum_or_capacity(self):
        readings = providers.parse_ipmi_sensors(SENSORS)
        self.assertEqual(readings["power_w"]["value"],200)
        self.assertEqual(sum(r["role"] == "power_w" for r in readings.values()),1)
        self.assertEqual(readings["hardware_health"]["value"],"red")
        self.assertTrue(any(r["role"] == "temperature:ambient" for r in readings.values()))
        no_total = providers.parse_ipmi_sensors(SENSORS.replace("System Level,200.000,Watts,ok\n",""))
        self.assertNotIn("power_w",no_total)
        self.assertFalse(any("Unavailable Temp" == r["label"] for r in readings.values()))

    def test_dcmi_current_not_average_or_deactivated(self):
        text="Instantaneous power reading: 170 Watts\nAverage power reading over sample period: 200 Watts\nPower reading state is: activated"
        self.assertEqual(providers.parse_dcmi_power(text),170)
        self.assertIsNone(providers.parse_dcmi_power(text.replace("activated","deactivated")))
        self.assertIsNone(providers.parse_dcmi_power("Average power reading over sample period: 200 Watts"))

    def test_ipmi_commands_are_read_only_and_password_not_in_arguments(self):
        calls=[]
        def run(command,**kwargs):
            calls.append((command,kwargs))
            if command[-1]=="sensor": return NS(returncode=0,stdout=SENSORS)
            if command[-1]=="reading": return NS(returncode=0,stdout="Instantaneous power reading: 180 Watts\nPower reading state is: activated")
            return NS(returncode=0,stdout="Chassis Power is on")
        with patch.dict("os.environ",{"TEST_SECRET":"example-secret"}),patch.object(providers.subprocess,"run",run):
            readings,metadata=providers.IPMIProvider(config()["sources"][0]).collect()
        self.assertEqual(readings["power_w"]["value"],180)
        self.assertEqual(metadata["power_method"],"dcmi")
        self.assertEqual(readings["power_state"]["value"],"poweredOn")
        for command,options in calls:
            self.assertNotIn("example-secret",str(command))
            self.assertNotIn("-P",command)
            self.assertEqual(options["env"]["IPMI_PASSWORD"],"example-secret")
            self.assertEqual(command[command.index("-C")+1],"3")
        self.assertEqual([c[0][-1] for c in calls],["sensor","reading","status"])

    def test_discovery_ids_topics_and_birth_are_stable(self):
        cfg=config();validate_config(cfg)
        mqtt=FakeMQTT();bridge=Bridge(cfg,mqtt)
        source=cfg["sources"][0]
        readings={"power_w":providers.metric(180,"W","Puissance serveur","power_w")}
        bridge.send(source,readings,{"power_method":"dcmi"})
        topic,payload=bridge.discovery_payload(source,"power_w",readings["power_w"])
        self.assertEqual(payload["device_class"],"power")
        self.assertEqual(payload["unit_of_measurement"],"W")
        self.assertEqual(payload["availability_mode"],"all")
        self.assertGreaterEqual(payload["expire_after"],180)
        self.assertIn("value_json.sample_time",payload["value_template"])
        self.assertEqual(topic,bridge.topics(source,"power_w")[2])
        states=[m for m in mqtt.messages if m[0].endswith("/state")]
        self.assertFalse(states[0][2]["retain"])
        self.assertEqual(json.loads(states[0][1])["values"]["power_w"],180)
        before=len(mqtt.messages)
        bridge.on_message(None,None,NS(topic="homeassistant/status",payload=b"online"))
        self.assertIn(topic,[item[0] for item in mqtt.messages[before:]])
        self.assertGreater(len(mqtt.messages),before)
        self.assertTrue(all(t.startswith(("infrastructure/test/","homeassistant/sensor/infra_")) for t,_,_ in mqtt.messages))
        bridge.send(source,{}, {})
        self.assertTrue(bridge.discovery, "temporary missing readings keep discovery IDs/history")
        self.assertFalse(any(payload=="" for _,payload,_ in mqtt.messages))

    def test_invalid_source_ids_and_duplicate_ids_rejected(self):
        for bad in ("r610/command","+","#",""):
            cfg=config();cfg["sources"][0]["id"]=bad
            with self.assertRaises(ValueError):validate_config(cfg)
        cfg=config();cfg["sources"]*=2
        with self.assertRaises(ValueError):validate_config(cfg)

    def test_actual_mqtt_template_renders_zero_unknown_and_stale(self):
        from jinja2 import Environment, StrictUndefined
        bridge=Bridge(config(),FakeMQTT())
        source=config()["sources"][0]
        # The payload key 'values' must not accidentally resolve to dict.values.
        env=Environment(undefined=StrictUndefined)
        env.globals.update(now=lambda:1000,as_timestamp=lambda timestamp:timestamp)
        for key in ("power_w",'filesystem:/mnt/"data":used'):
            template=env.from_string(bridge.discovery_payload(source,key,providers.metric(0,"W","Power"))[1]["value_template"])
            for value,expected in ((0,"0"),(180,"180"),(None,"None")):
                self.assertEqual(template.render(value_json={"sample_time":1000,"values":{key:value}}),expected)
            self.assertEqual(template.render(value_json={"sample_time":1000,"values":{}}),"None")
            self.assertEqual(template.render(value_json={"sample_time":1,"values":{key:180}}),"None")
            self.assertEqual(template.render(value_json={"sample_time":2000,"values":{key:180}}),"None")

    def test_linux_first_sample_unknown_then_cpu_and_network_deltas(self):
        files={"/proc/uptime":"1000 10", "/proc/stat":"cpu 100 0 100 800 0 0 0 0",
               "/proc/meminfo":"MemTotal: 1048576 kB\nMemAvailable: 524288 kB\n",
               "/proc/net/dev":"header\nheader\neth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0",
               "/sys/class/net/eth0/speed":"1000"}
        def read(path,*args,**kwargs):return files[path.as_posix()]
        with patch.object(Path,"read_text",read),patch.object(providers.shutil,"disk_usage",return_value=NS(total=100,used=40,free=60)),\
             patch.object(providers.subprocess,"run",side_effect=FileNotFoundError),patch.object(providers.time,"monotonic",side_effect=[10,20]):
            provider=providers.LinuxProvider({})
            first,_=provider.collect()
            files["/proc/stat"]="cpu 130 0 130 840 0 0 0 0"
            files["/proc/net/dev"]="header\nheader\neth0: 2000 0 0 0 0 0 0 0 4000 0 0 0 0 0 0 0"
            second,_=provider.collect()
        self.assertIsNone(first["cpu_used"]["value"])
        self.assertIsNone(first["net_rx:eth0"]["value"])
        self.assertEqual(second["cpu_used"]["value"],60)
        self.assertEqual(second["ram_percent"]["value"],50)
        self.assertEqual(second["net_rx:eth0"]["value"],0.0008)
        self.assertEqual(second["net_tx:eth0"]["value"],0.0016)
        self.assertEqual(second["filesystem:/:used"]["value"],40)


if __name__=="__main__":unittest.main()
