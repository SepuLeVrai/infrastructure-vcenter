/* Fusion/editor browser checks; test fixture only, no real broker or iDRAC. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require(process.argv[2]||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.argv[3]});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<style>body{margin:0;--primary-text-color:#eee;--secondary-text-color:#aaa;--divider-color:#444;--primary-color:#28bada;--ha-card-background:#222;--secondary-background-color:#333}</style>');
  await page.evaluate(()=>{window.loadCardHelpers=async()=>({createCardElement:()=>document.createElement('div')});});
  await page.addScriptTag({path:path.resolve('www/infra-vcenter/infrastructure-card.js')});
  await page.evaluate(()=>{
   window.states={};
   const add=(entity,value,attributes)=>states[entity]={entity_id:entity,state:String(value),attributes};
   const native=(entity,key,value,unit,extra={})=>add(entity,value,{integration_domain:'infra_vcenter',vcenter_id:'vc',resource_type:'host',resource_id:'h1',resource_name:'ESXi R610',metric_key:key,unit_of_measurement:unit,...extra});
   native('sensor.cpu','cpu_used',5,'%');native('sensor.ram','ram_percent',20,'%');
   native('sensor.memory','ram_used',20,'GiB');native('sensor.total','ram_total',100,'GiB');native('sensor.uptime','uptime',10000,'s');native('sensor.vms','vms_on',0);
   native('sensor.connection','connection','connected');native('sensor.health','health','red');
   native('sensor.temp','hardware:oldambient',20,'°C',{metric_name:'System Board 1 Ambient Temp'});
   const external=(entity,source,type,key,role,value,unit,label)=>add(entity,value,{integration_domain:'infra_agent',source_uid:'example:'+source,source_id:source,source_type:type,
    resource_type:type==='idrac'?'hardware':'standalone',resource_id:source,resource_name:source==='worker'?'LINUX-NODE-01':'iDRAC R610',
    metric_key:key,metric_role:role,metric_name:label,unit_of_measurement:unit,physical_nics:[]});
   external('sensor.ipmipower','idrac-r610','idrac','power_w','power_w',180,'W','Puissance serveur');
   external('sensor.ipmitemp','idrac-r610','idrac','hardware:newambient','temperature:ambient',23,'°C','Ambient Temp');
   external('sensor.ipmihealth','idrac-r610','idrac','hardware_health','hardware_health','green',undefined,'Santé capteurs IPMI');
   for(const [key,value,unit] of [['cpu_used',7,'%'],['ram_percent',25,'%'],['ram_used',8,'GiB'],['ram_total',32,'GiB'],['uptime',10000,'s'],['connection','connected'],['filesystem:/:used',40,'%'],['filesystem:/:free',100,'GiB']])
    external('sensor.worker_'+key.replace(/\W/g,'_'),'worker','standalone',key,key,value,unit,key);
   add('sensor.worker_plug',205,{unit_of_measurement:'W',friendly_name:'Prise Worker'});
   window.card=document.createElement('infra-vcenter-overview');document.body.append(card);card.setConfig({});card.hass={states};
  });
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelectorAll('.host-panel').length),2);
  assert.ok(await page.evaluate(()=>card.shadowRoot.textContent.includes('Sources iDRAC à rattacher')));
  await page.evaluate(()=>{
   window.editor=card.constructor.getConfigElement();document.body.append(editor);
   editor.setConfig({type:'custom:infra-vcenter-overview'});editor.hass={states};
   editor.addEventListener('config-changed',e=>window.edited=e.detail.config);
   [...editor.shadowRoot.querySelectorAll('button')].find(b=>b.textContent==='Ajouter un rattachement').click();
   const selects=editor.shadowRoot.querySelectorAll('.row select');selects[0].value='example:idrac-r610';selects[0].dispatchEvent(new Event('change'));
   const target=editor.shadowRoot.querySelectorAll('.row select')[1];target.value='vc:host:h1';target.dispatchEvent(new Event('change'));
   card.setConfig(edited);
  });
  assert.deepEqual(await page.evaluate(()=>edited.source_links),[{source:'example:idrac-r610',target:'vc:host:h1'}]);
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelectorAll('.host-panel').length),2);
  assert.equal(await page.evaluate(()=>card.shadowRoot.textContent.includes('Sources iDRAC à rattacher')),false);
  assert.ok(await page.evaluate(()=>card.shadowRoot.querySelector('.power-summary').textContent.includes('180 W')));
  assert.ok(await page.evaluate(()=>card.shadowRoot.querySelector('.power-summary').textContent.includes('1 / 2')));
  const temperatures=()=>page.evaluate(()=>[...card.shadowRoot.querySelector('.host-panel').querySelectorAll('.value')].map(e=>e.textContent).filter(t=>t.endsWith('°C')));
  assert.deepEqual(await temperatures(),['23 °C']);
  assert.ok(await page.evaluate(()=>card.shadowRoot.querySelector('.host-panel').textContent.includes('Critique')),'IPMI green must not hide vCenter critical');
  await page.evaluate(()=>{states['sensor.ipmitemp'].state='unavailable';card.hass={states};});
  assert.deepEqual(await temperatures(),['20 °C']);
  await page.evaluate(()=>{
   const labels=[...editor.shadowRoot.querySelectorAll('label')];
   const label=labels.find(l=>l.querySelector('select') && l.firstChild.nodeType===3 && l.firstChild.textContent==='LINUX-NODE-01');
   const select=label.querySelector('select');select.value='sensor.worker_plug';select.dispatchEvent(new Event('change'));card.setConfig(edited);
  });
  assert.equal(await page.evaluate(()=>edited.metric_overrides['source:example:worker'].power_w),'sensor.worker_plug');
  assert.ok(await page.evaluate(()=>card.shadowRoot.querySelector('.power-summary').textContent.includes('385 W')));
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>390),false);
  assert.deepEqual(errors,[]);
  console.log('Unified browser checks passed: visual editor persistence, ESXi/iDRAC merge, standalone, temperature dedup/fallback, independent health, partial watts, power override, mobile.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
