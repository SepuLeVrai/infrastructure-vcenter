const assert = require('node:assert/strict');
global.HTMLElement = class {};
global.customElements = {get: () => true};
global.window = {};
const {inventory, metricLabel, displayName, temperatureLabel} = require('../www/infra-vcenter/infrastructure-card.js');
const state = (entity_id, vc, kind, id, metric, extra = {}) => ({entity_id, state: '1',
  attributes: {integration_domain: 'infra_vcenter', vcenter_id: vc, resource_type: kind,
    resource_id: id, resource_name: id, metric_key: metric, ...extra}});
const states = {
  'sensor.a': state('sensor.a', 'vc1', 'vm', 'vm-1', 'cpu_mhz', {host_id: 'host-1'}),
  'sensor.b': state('sensor.b', 'vc1', 'vm', 'vm-1', 'ram_host', {host_id: 'host-1'}),
  'sensor.c': state('sensor.c', 'vc2', 'vm', 'vm-1', 'cpu_mhz', {host_id: 'host-2'}),
  'sensor.d': state('sensor.d', 'vc1', 'datastore', 'shared', 'used', {host_ids: ['host-1', 'host-2']}),
  'sensor.unrelated': {entity_id: 'sensor.unrelated', state: '7', attributes: {}}
};
assert.equal(inventory(states).length, 3, 'same VMware IDs in different vCenters stay distinct');
assert.equal(inventory(states, 'vc1').length, 2, 'optional vCenter filter');
let vm = inventory(states, 'vc1').find(r => r.kind === 'vm');
assert.deepEqual(Object.keys(vm.metrics).sort(), ['cpu_mhz', 'ram_host']);
assert.equal(vm.attrs.host_id, 'host-1');
for (const entity of ['sensor.a', 'sensor.b']) states[entity].attributes.host_id = 'host-2';
vm = inventory(states, 'vc1').find(r => r.kind === 'vm');
assert.equal(vm.attrs.host_id, 'host-2', 'membership follows a migration');
assert.deepEqual(inventory(states).find(r => r.kind === 'datastore').attrs.host_ids, ['host-1', 'host-2']);
assert.equal(metricLabel('net_rx:vmnic0', {attributes:{metric_name:'net_rx:vmnic0'}}), 'Réception');
assert.equal(metricLabel('net_tx:vmnic3'), 'Émission');
assert.equal(metricLabel('filesystem:C:\\:used'), 'C:\\ · Occupation');
assert.equal(metricLabel('filesystem:/:free'), '/ · Libre');
const host={key:'vc:host:h1',name:'192.0.2.21',attrs:{dns_hostname:'esx01'}};
assert.equal(displayName(host),'esx01');
assert.equal(displayName(host,{machine_names:{'vc:host:h1':'Serveur Cave'}}),'Serveur Cave');
assert.equal(displayName({...host,attrs:{}}),'192.0.2.21');
assert.equal(temperatureLabel('hardware:cpu',{attributes:{metric_name:'coretemp-isa-0000 · Package id 0'}}),'CPU · Package 0');
assert.equal(temperatureLabel('hardware:core',{attributes:{metric_name:'coretemp-isa-0000 · Core 3'}}),'Cœur 3');
assert.equal(temperatureLabel('hardware:zone',{attributes:{metric_name:'acpitz-acpi-0 · temp2'}}),'Zone ACPI 2');
console.log('Dashboard grouping checks passed (discovery, multiple vCenters, shared datastore, migration).');
