"""Network collection with actual SDK query types and synthetic responses."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import unittest
from test_client import client


def counter(ident, name):
    return NS(key=ident, groupInfo=NS(key="net"), nameInfo=NS(key=name),
              unitInfo=NS(key="kiloBytesPerSecond"), rollupType="average")


def records():
    return {
        "host:h1": {"id": "h1", "kind": "host", "metrics": {"connection": ("connected", None)}, "attributes": {}},
        "vm:v1": {"id": "v1", "kind": "vm", "metrics": {"power_state": ("poweredOn", None)}, "attributes": {}},
        "vm:off": {"id": "off", "kind": "vm", "metrics": {"power_state": ("poweredOff", None)}, "attributes": {}},
    }


class NetworkTests(unittest.TestCase):
    def test_queries_scaling_zero_and_instances(self):
        data = records()
        def query(querySpec):
            self.assertEqual(len(querySpec), 2)
            samples = []
            for spec in querySpec:
                self.assertEqual(spec.intervalId, 20)
                self.assertEqual(spec.maxSample, 1)
                host = isinstance(spec.entity, client.vim.HostSystem)
                instance = "vmnic0" if host else ""
                samples.append(NS(entity=spec.entity, sampleInfo=[NS(timestamp=datetime.now(timezone.utc))], value=[
                    NS(id=NS(counterId=1, instance=instance), value=[1024]),
                    NS(id=NS(counterId=2, instance=instance), value=[0]),
                    NS(id=NS(counterId=1, instance="aggregate-ignored"), value=[-1]),
                ] if host else [NS(id=NS(counterId=1, instance=""), value=[-1])]))
            return samples
        content = NS(rootFolder=client.vim.Folder("root"),
                     perfManager=NS(perfCounter=[counter(1, "received"), counter(2, "transmitted")], QueryPerf=query))
        client.VCenterClient({}).collect_network(content, data)
        self.assertEqual(data["host:h1"]["metrics"]["net_rx:vmnic0"], (8.3886, "Mbit/s"))
        self.assertEqual(data["host:h1"]["metrics"]["net_tx:vmnic0"][0], 0)
        self.assertNotIn("net_rx:aggregate-ignored", data["host:h1"]["metrics"])
        self.assertIsNone(data["vm:v1"]["metrics"]["net_rx"][0])
        self.assertEqual(data["vm:off"]["attributes"]["network_collection"], "offline")

    def test_denied_statistics_do_not_break_other_metrics(self):
        data = records()
        def denied(**kw):
            raise client.vim.fault.NoPermission()
        content = NS(rootFolder=client.vim.Folder("root"),
                     perfManager=NS(perfCounter=[counter(1, "received")], QueryPerf=denied))
        client.VCenterClient({}).collect_network(content, data)
        self.assertIn("NoPermission", data["host:h1"]["attributes"]["network_collection"])
        self.assertEqual(data["host:h1"]["metrics"]["connection"][0], "connected")

    def test_stale_samples_not_published(self):
        data = records()
        def stale(querySpec):
            return [NS(entity=spec.entity, sampleInfo=[NS(timestamp=datetime.now(timezone.utc)-timedelta(hours=1))],
                       value=[NS(id=NS(counterId=1, instance="vmnic0"), value=[100])]) for spec in querySpec]
        content = NS(rootFolder=client.vim.Folder("root"),
                     perfManager=NS(perfCounter=[counter(1, "received")], QueryPerf=stale))
        client.VCenterClient({}).collect_network(content, data)
        self.assertEqual(data["host:h1"]["attributes"]["network_collection"], "stale")
        self.assertNotIn("net_rx:vmnic0", data["host:h1"]["metrics"])


if __name__ == "__main__":
    unittest.main()
