"""Discovered devices and sensors, including resources added after setup."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LABELS = {
    "power_state": "Alimentation", "health": "Santé", "cpu_mhz": "CPU utilisé",
    "vcpu": "vCPU", "ram_configured": "RAM configurée", "ram_active": "RAM active estimée",
    "ram_host": "RAM consommée sur hôte", "uptime": "Uptime", "tools": "VMware Tools",
    "storage_committed": "Stockage engagé", "storage_uncommitted": "Stockage non engagé",
    "snapshots": "Snapshots", "connection": "Connexion", "maintenance": "Maintenance",
    "cpu_used": "CPU utilisé", "ram_used": "RAM utilisée", "ram_total": "RAM totale",
    "ram_percent": "RAM utilisée", "accessible": "Accessible", "capacity": "Capacité",
    "free": "Espace libre", "used": "Occupation", "vms": "VM", "hosts": "Hyperviseurs",
    "datastores": "Datastores",
    "vms_on": "VM allumées", "hosts_connected": "Hyperviseurs connectés",
    "storage_capacity": "Capacité totale datastores", "storage_free": "Espace libre datastores",
    "net_rx": "Réseau réception", "net_tx": "Réseau émission",
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        entities = []
        for resource, record in coordinator.data.items():
            for metric in record["metrics"]:
                key = (resource, metric)
                if key not in known:
                    known.add(key)
                    entities.append(InfrastructureSensor(coordinator, entry, resource, metric))
        async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class InfrastructureSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, resource, metric):
        super().__init__(coordinator)
        self.resource, self.metric = resource, metric
        record = coordinator.data[resource]
        endpoint = record["attributes"].get("source_endpoint")
        direct_group = record["attributes"].get("api_type") == "HostAgentGroup"
        self.vcenter_id = "esxi-direct" if endpoint or direct_group else entry.unique_id
        device_id = (f"esxi:{endpoint}:{record['kind']}:{record['attributes']['native_resource_id']}" if endpoint
                     else f"{entry.unique_id}:{resource}")
        self._attr_unique_id = f"{device_id}:{metric}"
        self._attr_name = record["attributes"].get("metric_labels", {}).get(metric) or LABELS.get(metric, metric.replace("net_rx:", "Réception · ").replace("net_tx:", "Émission · ").replace(":", " · "))
        self._attr_native_unit_of_measurement = record["metrics"][metric][1]
        unit = self._attr_native_unit_of_measurement
        if unit in ("GiB", "MHz", "%", "°C", "W", "V", "A", "rpm", "s", "Mbit/s"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        classes = {"GiB": SensorDeviceClass.DATA_SIZE, "MHz": SensorDeviceClass.FREQUENCY,
                   "°C": SensorDeviceClass.TEMPERATURE, "W": SensorDeviceClass.POWER,
                   "V": SensorDeviceClass.VOLTAGE, "A": SensorDeviceClass.CURRENT,
                   "s": SensorDeviceClass.DURATION, "Mbit/s": SensorDeviceClass.DATA_RATE}
        self._attr_device_class = classes.get(unit)
        self._attr_entity_registry_enabled_default = not metric.startswith("hardware:") or unit == "°C"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=record["name"], manufacturer=record["attributes"].get("vendor") or "VMware",
            model=record["attributes"].get("model") or record["kind"],
        )

    @property
    def available(self):
        return (super().available and self.resource in self.coordinator.data
                and self.coordinator.data[self.resource].get("available", True)
                and self.metric in self.coordinator.data[self.resource]["metrics"])

    @property
    def native_value(self):
        return self.coordinator.data.get(self.resource, {}).get("metrics", {}).get(self.metric, (None, None))[0]

    @property
    def extra_state_attributes(self):
        record = self.coordinator.data.get(self.resource, {})
        # Static context only: do not repeat the whole inventory on every entity.
        return {"resource_type": record.get("kind"), "resource_id": record.get("id"),
                "resource_name": record.get("name"), "partial_collection": record.get("partial"),
                "integration_domain": DOMAIN, "vcenter_id": self.vcenter_id,
                "metric_key": self.metric,
                "metric_name": record.get("attributes", {}).get("metric_labels", {}).get(self.metric) or LABELS.get(self.metric, self.metric),
                **{key: val for key, val in record.get("attributes", {}).items()
                   if key in ("host_id", "host_name", "host_ids", "host_names", "datastore_ids", "network_collection", "network_sample_time")},
                **(record.get("attributes", {}) if self.metric in ("health", "vms") else {})}
