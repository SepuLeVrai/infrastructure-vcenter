/* Dedicated standalone layout and machine-name checks, simulated HA graphs. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.argv[2]||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.argv[3]});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<style>body{margin:0;background:#111;--primary-text-color:#eee;--secondary-text-color:#aaa;--divider-color:#444;--primary-color:#28bada;--ha-card-background:#222;--secondary-background-color:#303030}</style>');
  await page.evaluate(()=>{
   window.graphConfigs=[];
   window.loadCardHelpers=async()=>({createCardElement:config=>{
    graphConfigs.push(config);const card=document.createElement('div');card.style.cssText='border:1px dashed #456;border-radius:10px;padding:18px;min-height:190px';
    card.textContent=config.title+' · historique natif simulé';return card;
   }});
  });
  await page.addScriptTag({path:path.resolve('www/infra-vcenter/infrastructure-card.js')});
  await page.evaluate(()=>{
   window.states={};
   const add=(key,value,unit,label)=>{
    const entity_id='sensor.worker_'+key.replace(/\W/g,'_');
    states[entity_id]={entity_id,state:String(value),attributes:{integration_domain:'infra_agent',source_uid:'example:worker',source_type:'standalone',resource_type:'standalone',resource_id:'worker',resource_name:'LINUX-NODE-01',metric_key:key,metric_role:key,metric_name:label||key,unit_of_measurement:unit,
      model:'Linux',physical_nics:[{device:'eno1',speed_mbps:1000}]}};
   };
   for(const [key,value,unit]of [['cpu_used',.45,'%'],['ram_percent',3.72,'%'],['ram_used',.58,'GiB'],['ram_total',15.52,'GiB'],['uptime',97132,'s'],['connection','connected'],['net_rx:eno1',.04,'Mbit/s'],['net_tx:eno1',.03,'Mbit/s'],['filesystem:/:used',14.81,'%'],['filesystem:/:free',44.31,'GiB']])add(key,value,unit);
   add('hardware:package',32,'°C','coretemp-isa-0000 · Package id 0');
   for(let n=0;n<4;n++)add('hardware:core'+n,28+n,'°C','coretemp-isa-0000 · Core '+n);
   for(let n=1;n<=2;n++)add('hardware:acpi'+n,26+n,'°C','acpitz-acpi-0 · temp'+n);
   const native=(key,value,unit,extra={})=>{const entity_id='sensor.esx_'+key;states[entity_id]={entity_id,state:String(value),attributes:{integration_domain:'infra_vcenter',vcenter_id:'vc',resource_type:'host',resource_id:'h1',resource_name:'192.0.2.21',metric_key:key,unit_of_measurement:unit,...extra}};};
   native('connection','connected');native('health','green',undefined,{dns_hostname:'esx01',dns_name:'esx01.example.invalid'});native('cpu_used',10,'%');native('ram_percent',20,'%');native('ram_used',20,'GiB');native('ram_total',100,'GiB');native('uptime',10000,'s');native('vms_on',0);
   window.card=document.createElement('infra-vcenter-overview');document.body.append(card);card.setConfig({});card.hass={states};
  });
  await page.waitForFunction(()=>graphConfigs.some(c=>c.title==='Réseau · Mbit/s'));
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.standalone-panel .worker-stats').children.length),5);
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelectorAll('.standalone-panel .probe-chips .measure').length),6,'four cores and two ACPI zones remain visible');
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.standalone-panel').textContent.includes('coretemp-isa')),false);
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.standalone-panel').textContent.includes('acpitz-acpi')),false);
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.host-panel h2').textContent),'esx01');
  assert.ok(await page.evaluate(()=>card.shadowRoot.querySelector('.host-panel').textContent.includes('192.0.2.21')),'IP retained as secondary context');
  await page.evaluate(()=>[...card.shadowRoot.querySelectorAll('.worker-tabs button')].find(b=>b.textContent==='Températures').click());
  await page.waitForFunction(()=>graphConfigs.some(c=>c.title==='Zones thermiques ACPI · °C'));
  const thermal=await page.evaluate(()=>graphConfigs.filter(c=>c.title.includes('CPU · °C')||c.title.includes('ACPI · °C')));
  assert.equal(thermal.find(c=>c.title==='Températures CPU · °C').entities.length,1,'package-only plot by default');
  assert.equal(thermal.find(c=>c.title==='Zones thermiques ACPI · °C').entities.length,2);
  assert.deepEqual(thermal.find(c=>c.title==='Zones thermiques ACPI · °C').entities.map(e=>e.name),['Zone ACPI 1','Zone ACPI 2']);
  await page.evaluate(()=>{const toggle=card.shadowRoot.querySelector('.core-curves-toggle input');toggle.checked=true;toggle.dispatchEvent(new Event('change'));});
  await page.waitForFunction(()=>graphConfigs.some(c=>c.title==='Températures CPU · °C'&&c.entities.length===5));
  await page.evaluate(()=>{states['sensor.worker_cpu_used'].state='1';card.hass={states};});
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.core-curves-toggle input').checked),true,'choice survives a measurement refresh');
  await page.evaluate(()=>{
   window.editor=card.constructor.getConfigElement();document.body.append(editor);editor.setConfig({type:'custom:infra-vcenter-overview',source_links:[{source:'example:idrac-r610',target:'vc:host:h1'}]});editor.hass={states};
   editor.addEventListener('config-changed',e=>window.edited=e.detail.config);
   const input=editor.shadowRoot.querySelector('input[data-machine="vc:host:h1"]');input.value='ESXi node 1';input.dispatchEvent(new Event('change'));card.setConfig(edited);editor.remove();
  });
  assert.equal(await page.evaluate(()=>card.shadowRoot.querySelector('.host-panel h2').textContent),'ESXi node 1');
  assert.deepEqual(await page.evaluate(()=>edited.source_links),[{source:'example:idrac-r610',target:'vc:host:h1'}],'renaming must preserve source links');
  fs.mkdirSync('dist',{recursive:true});
  await page.locator('infra-vcenter-overview').screenshot({path:'dist/qa-worker-0.3.1-desktop.png'});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>390),false);
  await page.locator('infra-vcenter-overview').screenshot({path:'dist/qa-worker-0.3.1-mobile.png'});
  assert.deepEqual(errors,[]);
  console.log('Worker checks passed: compact package/core/ACPI values, usage/thermal tabs, separated CPU/ACPI plots, optional core curves, persistent choices, DNS/custom names, source-link preservation and mobile layout.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
