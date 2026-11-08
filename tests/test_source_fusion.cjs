const assert=require('node:assert/strict');
global.HTMLElement=class{};global.customElements={get:()=>true};global.window={};
const {inventory,powerSummary}=require('../www/infra-vcenter/infrastructure-card.js');
const s=(id,value,attrs)=>({entity_id:id,state:String(value),attributes:attrs});
const native=(id,key,value,unit,extra={})=>s(id,value,{integration_domain:'infra_vcenter',vcenter_id:'vc1',resource_type:'host',resource_id:'h1',resource_name:'ESXi R610',metric_key:key,unit_of_measurement:unit,...extra});
const ext=(id,source,type,key,role,value,unit,label)=>s(id,value,{integration_domain:'infra_agent',source_uid:`example:${source}`,source_id:source,source_type:type,
  resource_type:type==='idrac'?'hardware':'standalone',resource_id:source,resource_name:source,metric_key:key,metric_role:role,metric_name:label,unit_of_measurement:unit});
const states={
 'sensor.cpu':native('sensor.cpu','cpu_used',5,'%'),
 'sensor.temp':native('sensor.temp','hardware:bmc-1',20,'°C',{metric_name:'System Board 1 Ambient Temp'}),
 'sensor.power':ext('sensor.power','idrac-r610','idrac','power_w','power_w',180,'W','Puissance serveur'),
 'sensor.itemp':ext('sensor.itemp','idrac-r610','idrac','hardware:ambient','temperature:ambient',23,'°C','Ambient Temp'),
 'sensor.psu':ext('sensor.psu','idrac-r610','idrac','hardware:psu1','component_power:psu1',100,'W','PS1 Power'),
 'sensor.worker':ext('sensor.worker','worker','standalone','cpu_used','cpu_used',7,'%','CPU'),
 'sensor.workerpower':ext('sensor.workerpower','worker','standalone','power_w','power_w',50,'W','Puissance serveur'),
 'sensor.plug':s('sensor.plug',170,{unit_of_measurement:'W'}),
};
const config={source_links:[{source:'example:idrac-r610',target:'vc1:host:h1'}]};
let resources=inventory(states,undefined,config);
assert.equal(resources.length,2,'one ESXi plus one standalone; linked iDRAC is not a second server');
let host=resources.find(r=>r.kind==='host');
assert.equal(host.metrics['temperature:ambient'].entity_id,'sensor.itemp');
assert.equal(Object.values(host.metrics).filter(s=>s.attributes.unit_of_measurement==='°C').length,1);
assert.equal(host.metrics.power_w.state,'180');
assert.equal(host.metrics.cpu_used.entity_id,'sensor.cpu');
assert.equal(states['sensor.temp'].attributes.metric_key,'hardware:bmc-1','raw states must not be modified');
assert.deepEqual(powerSummary(resources),{watts:230,measured:2,total:2},'component watts must not be summed');
states['sensor.itemp'].state='unavailable';
host=inventory(states,undefined,config).find(r=>r.kind==='host');
assert.equal(host.metrics['temperature:ambient'].entity_id,'sensor.temp','fallback to fresh native sensor');
const override={...config,metric_overrides:{'vc1:host:h1':{power_w:'sensor.plug'}}};
host=inventory(states,undefined,override).find(r=>r.kind==='host');
assert.equal(host.metrics.power_w.entity_id,'sensor.plug');
states['sensor.plug'].state='0';
assert.equal(inventory(states,undefined,override).find(r=>r.kind==='host').metrics.power_w.state,'0','real zero remains valid');
states['sensor.plug'].state='unavailable';
assert.equal(inventory(states,undefined,override).find(r=>r.kind==='host').metrics.power_w.entity_id,'sensor.power');
states['sensor.plug'].state='-1';
assert.equal(inventory(states,undefined,override).find(r=>r.kind==='host').metrics.power_w.entity_id,'sensor.power','negative power is invalid');
states['sensor.workerpower'].state='unavailable';
assert.deepEqual(powerSummary(inventory(states,undefined,config)),{watts:180,measured:1,total:2},'partial coverage stays explicit');
const unpaired=inventory(states);
assert.ok(unpaired.some(r=>r.kind==='hardware'));
assert.deepEqual(powerSummary(unpaired),{watts:null,measured:0,total:2},'unpaired source is never counted');
assert.ok(inventory(states,undefined,{source_links:[...config.source_links,...config.source_links]}).some(r=>r.kind==='hardware'),'ambiguous links are not guessed');
console.log('Source fusion checks passed: one machine, deduplication, fallback, true zero, explicit override, partial watts, no PSU sum, raw-state preservation, unpaired/ambiguous sources.');
