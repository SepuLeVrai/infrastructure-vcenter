"""Offline collector checks using the real VMware SDK and synthetic inventory."""
import importlib.util
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace as NS
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".dev-deps"))
spec = importlib.util.spec_from_file_location("collector", ROOT / "custom_components/infra_vcenter/client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class CollectorTests(unittest.TestCase):
    def test_unknown_and_zero_are_distinct(self):
        self.assertIsNone(client.ratio(None, 100))
        self.assertIsNone(client.ratio(5, 0))
        self.assertEqual(client.ratio(0, 100), 0)
        self.assertIsNone(client.mib_to_gib(-1))
        self.assertEqual(client.bytes_to_gib(1024**3), 1)

    def test_sensor_unit_scaling(self):
        sensor = NS(baseUnits="degrees C", rateUnits="none", currentReading=275, unitModifier=-1)
        self.assertEqual(client.numeric_sensor(sensor), (27.5, "°C"))
        sensor.baseUnits = "unspecified"
        self.assertIsNone(client.numeric_sensor(sensor))

    def test_configured_dns_names(self):
        self.assertEqual(client.dns_names(None),(None,None))
        self.assertEqual(client.dns_names(NS(hostName="esx01",domainName="example.invalid")),("esx01","esx01.example.invalid"))
        self.assertEqual(client.dns_names(NS(hostName="esx01.example.invalid.",domainName="example.invalid.")),("esx01.example.invalid","esx01.example.invalid"))
        self.assertEqual(client.dns_names(NS(hostName="192.0.2.21",domainName="example.invalid")),(None,None))

    def test_inventory_and_stale_offline_metrics(self):
        class Fake(client.VCenterClient):
            @contextmanager
            def session(self):
                yield NS(about=NS(instanceUuid="vc-1", version="6.7.0", build="12345678", apiVersion="6.7"))

            def inventory(self, content, kind, paths):
                if kind == client.vim.VirtualMachine:
                    return [("vm-1", {"name": "test", "runtime": NS(powerState="poweredOff"),
                        "summary": NS(quickStats=NS(overallCpuUsage=100, guestMemoryUsage=512),
                                      config=NS(memorySizeMB=2048, numCpu=2)),
                        "guest": NS(disk=[NS(diskPath="/", capacity=1024**3, freeSpace=512*1024**2)])}, False)]
                if kind == client.vim.HostSystem:
                    return [("host-1", {"name": "esx", "runtime.connectionState": "connected",
                        "config.network.dnsConfig": NS(hostName="esx01",domainName="example.invalid"),
                        "summary": NS(hardware=NS(cpuMhz=2000, numCpuCores=4, memorySize=8*1024**3),
                                      quickStats=NS(overallCpuUsage=4000, overallMemoryUsage=2048))}, False)]
                return [("ds-1", {"name": "data", "summary": NS(capacity=10*1024**3,
                            freeSpace=4*1024**3, accessible=True)}, False)]

        result = Fake({}).collect()
        vm = result["vm:vm-1"]["metrics"]
        self.assertIsNone(vm["cpu_mhz"][0])
        self.assertIsNone(vm["filesystem:/:used"][0])
        self.assertEqual(vm["ram_configured"][0], 2)
        host = result["host:host-1"]["metrics"]
        self.assertEqual(host["cpu_used"][0], 50)
        self.assertEqual(host["ram_percent"][0], 25)
        self.assertEqual(result["host:host-1"]["attributes"]["dns_hostname"],"esx01")
        self.assertEqual(result["host:host-1"]["attributes"]["dns_name"],"esx01.example.invalid")
        self.assertEqual(result["datastore:ds-1"]["metrics"]["used"][0], 60)
        self.assertEqual(result["vcenter:vc-1"]["metrics"]["vms"][0], 1)

    def test_bulk_pagination_and_view_cleanup(self):
        view = NS(destroyed=False)
        view.Destroy = lambda: setattr(view, "destroyed", True)
        # Build actual VMware FilterSpec types using a real managed object reference.
        managed_view = client.vim.view.ContainerView("view-1")
        pc = NS(pages=0)
        pc.RetrievePropertiesEx = lambda **kw: NS(objects=[NS(obj=NS(_moId="vm-1"),
            propSet=[NS(name="name", val="one")], missingSet=[])], token="next")
        def next_page(**kw):
            self.assertEqual(kw["token"], "next")
            return NS(objects=[NS(obj=NS(_moId="vm-2"), propSet=[], missingSet=["denied"])], token=None)
        pc.ContinueRetrievePropertiesEx = next_page
        # Patch only the managed view Destroy method through a stand-in factory.
        from unittest.mock import patch
        with patch.object(client.vim.view.ContainerView, "Destroy", lambda self: setattr(view, "destroyed", True)):
            content = NS(rootFolder=client.vim.Folder("root"), propertyCollector=pc,
                         viewManager=NS(CreateContainerView=lambda *a: managed_view))
            rows = client.VCenterClient({}).inventory(content, client.vim.VirtualMachine, ["name"])
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1][2])
        self.assertTrue(view.destroyed)

    def test_shared_storage_and_vm_migration(self):
        class Fake(client.VCenterClient):
            target = "host-1"
            @contextmanager
            def session(self):
                yield NS(about=NS(instanceUuid="vc-1", version="6.7.0", build="12345678", apiVersion="6.7"))

            def inventory(self, content, kind, paths):
                if kind == client.vim.VirtualMachine:
                    return [("vm-1", {"name": "moving", "runtime": NS(powerState="poweredOn", host=NS(_moId=self.target)),
                            "datastore": [NS(_moId="shared")]}, False)]
                if kind == client.vim.HostSystem:
                    return [(ident, {"name": ident, "runtime.connectionState": "connected"}, False)
                            for ident in ("host-1", "host-2")]
                return [("shared", {"name": "Shared", "summary": NS(capacity=10*1024**3,
                    freeSpace=4*1024**3, accessible=True), "host": [NS(key=NS(_moId=h))
                    for h in ("host-1", "host-2")]}, False)]

        fake = Fake({})
        result = fake.collect()
        self.assertEqual(result["vm:vm-1"]["attributes"]["host_name"], "host-1")
        self.assertEqual(result["vm:vm-1"]["attributes"]["datastore_ids"], ["shared"])
        self.assertEqual(result["datastore:shared"]["attributes"]["host_ids"], ["host-1", "host-2"])
        self.assertEqual(result["vcenter:vc-1"]["metrics"]["storage_capacity"][0], 10)
        self.assertEqual(result["vcenter:vc-1"]["metrics"]["storage_free"][0], 4)
        self.assertEqual(result["host:host-1"]["metrics"]["vms"][0], 1)
        self.assertEqual(result["host:host-2"]["metrics"]["vms"][0], 0)
        selected = Fake({"esx_hosts": "host-1"}).collect()
        self.assertNotIn("host:host-2", selected)
        self.assertIn("vm:vm-1", selected)
        self.assertEqual(selected["datastore:shared"]["attributes"]["host_ids"], ["host-1"])
        self.assertEqual(selected["vcenter:vc-1"]["metrics"]["storage_capacity"][0], 10)
        self.assertEqual(selected["vcenter:vc-1"]["attributes"]["scope"], "selected_hosts")
        with self.assertRaises(client.HostSelectionError):
            Fake({"esx_hosts": "absent"}).collect()
        fake.target = "host-2"
        result = fake.collect()
        self.assertEqual(result["vm:vm-1"]["attributes"]["host_name"], "host-2")
        self.assertEqual(result["host:host-1"]["metrics"]["vms"][0], 0)
        self.assertEqual(result["host:host-2"]["metrics"]["vms_on"][0], 1)


if __name__ == "__main__":
    unittest.main()
