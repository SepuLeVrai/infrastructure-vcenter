/* Browser smoke test with simulated states and a stub for HA's native graphs. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {chromium} = require(process.argv[2] || 'playwright');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.argv[3]});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(`<style>body{margin:0;background:#101820;--primary-text-color:#e9f0f5;--secondary-text-color:#9aabb9;--ha-card-background:#17232f;--secondary-background-color:#1c2b39;--divider-color:#304253;--primary-color:#42c3de;--text-primary-color:#06222e}</style>`);
    await page.evaluate(() => {
      window.graphConfigs = [];
      window.loadCardHelpers = async () => ({createCardElement: config => {
        window.graphConfigs.push(config);
        const card = document.createElement('div');
        card.style.cssText='border:1px dashed #456;padding:20px;min-height:100px;border-radius:12px';
        card.textContent = config.title + ' · graphique natif simulé pour le test';
        return card;
      }});
    });
    await page.addScriptTag({path:path.resolve(process.argv[4] || 'www/infra-vcenter/infrastructure-card.js')});
    await page.evaluate(() => {
      const states = {};
      function add(kind, id, name, metrics, extra = {}) {
        for (const [metric, [value, unit]] of Object.entries(metrics)) {
          const entity_id = `sensor.${id}_${metric.replace(/[^a-z0-9]/gi,'_')}`;
          states[entity_id] = {entity_id, state:String(value), attributes:{integration_domain:'infra_vcenter',
            vcenter_id:'demo',resource_type:kind,resource_id:id,resource_name:name,metric_key:metric,
            unit_of_measurement:unit,...extra}};
        }
      }
      add('vcenter','vc','vCenter',{hosts:[2],hosts_connected:[2],vms:[2],vms_on:[2],datastores:[2],storage_capacity:[1500,'GiB'],storage_free:[700,'GiB']},
        {version:'6.7.0',build:'12345678',api_version:'6.7'});
      const hostMetrics = {connection:['connected'],health:['green'],cpu_used:[24,'%'],ram_percent:[72,'%'],
        ram_used:[46,'GiB'],ram_total:[64,'GiB'],uptime:[234567,'s'],vms_on:[1],
        'hardware:Ambient':[26,'°C'],'net_rx:vmnic0':[80,'Mbit/s'],'net_tx:vmnic0':[40,'Mbit/s']};
      for(let n=1;n<4;n++) {
        hostMetrics[`net_rx:vmnic${n}`]=[n/10,'Mbit/s']; hostMetrics[`net_tx:vmnic${n}`]=[0,'Mbit/s'];
      }
      for (const [id,name,model] of [['h1','192.0.2.21','PowerEdge R610'],['h2','192.0.2.22','PowerEdge R710']])
        add('host',id,name,hostMetrics,{model,esxi_version:'6.7.0',network_collection:'ok',
          physical_nics:Array.from({length:4},(_,n)=>({device:`vmnic${n}`,key:`p${n}`,speed_mbps:1000,full_duplex:true})),
          vswitches:[{name:'vSwitch0',uplink_keys:['p0'],mtu:1500}]});
      add('datastore','shared','Datastore partagé',{used:[60,'%'],capacity:[1000,'GiB'],free:[400,'GiB'],accessible:['on']},{host_ids:['h1','h2']});
      add('datastore','local','SSD local',{used:[40,'%'],capacity:[500,'GiB'],free:[300,'GiB'],accessible:['on']},{host_ids:['h1']});
      for (const [id,name,host] of [['v1','VM-01','h1'],['v2','VM <img src=x onerror="window.pwn=1">','h2']])
        add('vm',id,name,{power_state:['poweredOn'],health:['green'],cpu_mhz:[250,'MHz'],vcpu:[2],uptime:[234567,'s'],ram_host:[2,'GiB'],ram_active:[.7,'GiB'],ram_configured:[2,'GiB'],storage_committed:[25,'GiB'],storage_uncommitted:[18,'GiB'],snapshots:[0],net_rx:[2,'Mbit/s'],net_tx:[.3,'Mbit/s'],tools:['guestToolsRunning'],'filesystem:/:used':[14.5,'%'],'filesystem:/:free':[25,'GiB']},
          {host_id:host,datastore_ids:['shared']});
      const card = document.createElement('infra-vcenter-overview');
      document.body.append(card); card.setConfig({hours_to_show:24}); card.hass = {states};
      window.card = card; window.fixture = states;
      card.addEventListener('hass-more-info', event => {window.lastInfo = event.detail.entityId;});
    });
    await page.waitForFunction(() => window.graphConfigs.length >= 6);
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelectorAll('table tbody tr').length),2);
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelectorAll('.gauge-button').length),3);
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelectorAll('img').length),0);
    assert.equal(await page.evaluate(() => window.pwn),undefined);
    assert.equal(await page.evaluate(() => graphConfigs.some(c => /datastore/i.test(c.title))),false);
    for (const width of [1440,1280,1100]) {
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(() => {
        const nics = [...card.shadowRoot.querySelector('.nic-grid').children];
        return new Set(nics.map(n => Math.round(n.getBoundingClientRect().top))).size;
      }),1,`four NICs must fit one line at ${width}px`);
    }
    await page.setViewportSize({width:1440,height:1100});
    assert.equal(await page.evaluate(() => {
      const graphs=[...card.shadowRoot.querySelector('.host-charts').children];
      return new Set(graphs.map(n => Math.round(n.getBoundingClientRect().top))).size;
    }),1,'host CPU/RAM and temperature graphs must share a line');
    assert.ok(await page.evaluate(() => graphConfigs.filter(c => /vmnic/.test(c.title)).every(c => c.entities.map(e => e.name).join(',')==='Réception,Émission')));
    await page.evaluate(() => card.shadowRoot.querySelector('.vm-name').click());
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelectorAll('.vm-detail-panel').length),1);
    await page.evaluate(() => card.shadowRoot.querySelector('.vm-detail-panel .measure').click());
    assert.ok(await page.evaluate(() => window.lastInfo));
    await page.waitForFunction(() => graphConfigs.some(c => c.title === 'CPU · MHz'));
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelector('.vm-detail-panel').textContent.includes('guestToolsRunning')),false);
    assert.ok(await page.evaluate(() => card.shadowRoot.querySelector('.vm-detail-panel').textContent.includes('En cours')));
    assert.ok(await page.evaluate(() => card.shadowRoot.querySelector('.volumes').textContent.includes('Espace libre')));
    await page.evaluate(() => card.shadowRoot.querySelector('.close-detail').click());
    assert.equal(await page.evaluate(() => card.shadowRoot.querySelectorAll('.vm-detail-panel').length),0);
    await page.evaluate(() => card.shadowRoot.querySelector('.vm-name').click());
    await page.evaluate(() => [...card.shadowRoot.querySelectorAll('.periods button')].find(b => b.textContent === '7 j').click());
    await page.waitForFunction(() => graphConfigs.some(c => c.hours_to_show === 168));
    // Follow a simulated vMotion without changing entity IDs or card configuration.
    await page.evaluate(() => {
      for (const state of Object.values(fixture)) if(state.attributes.resource_id === 'v1') state.attributes.host_id='h2';
      card.hass={states:fixture};
    });
    assert.deepEqual(await page.evaluate(() => [...card.shadowRoot.querySelectorAll('table tbody')].map(b => b.children.length)),[0,2]);
    fs.mkdirSync('dist',{recursive:true});
    const prefix=process.argv[5]||'qa-infrastructure';
    await page.screenshot({path:`dist/${prefix}-desktop.png`,fullPage:true});
    await page.setViewportSize({width:800,height:1100});
    assert.equal(await page.evaluate(() => new Set([...card.shadowRoot.querySelector('.nic-grid').children].map(n => Math.round(n.getBoundingClientRect().top))).size),2);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => new Set([...card.shadowRoot.querySelector('.nic-grid').children].map(n => Math.round(n.getBoundingClientRect().top))).size),4);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > 390),false,'mobile page must not overflow');
    await page.screenshot({path:`dist/${prefix}-mobile.png`,fullPage:true});
    await page.evaluate(() => {
      for (const state of Object.values(fixture)) if(state.attributes.resource_type === 'vcenter') {
        state.attributes.api_type='HostAgentGroup';
        state.attributes.unavailable_endpoints=[{host:'192.0.2.11',error:'TimeoutError'}];
      }
      card.hass={states:fixture};
    });
    assert.ok(await page.evaluate(() => card.shadowRoot.textContent.includes('ESXi')));
    assert.equal(await page.evaluate(() => card.shadowRoot.textContent.includes('Capacité totale')),false,'direct mode must not sum potentially shared datastores');
    assert.deepEqual(errors,[]);
    console.log('Browser checks passed: four NICs per desktop line, tablet/mobile layout, paired host graphs, readable labels, VM selection/closing, gauges, history configuration, entity clicks, migration, safe text. Native HA graphs are stubbed.');
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
