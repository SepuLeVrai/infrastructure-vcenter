/* Infrastructure vCenter 0.4.0 - local Lovelace card, no external dependencies. */
(() => {
  const TAG = "infra-vcenter-overview";
  const TEXT = { poweredOn: "Allumée", poweredOff: "Éteinte", suspended: "Suspendue",
    connected: "Connecté", disconnected: "Déconnecté", notResponding: "Sans réponse",
    green: "OK", yellow: "Avertissement", red: "Critique", gray: "Non évalué",
    unknown: "Inconnu", unavailable: "Indisponible", on: "Oui", off: "Non",
    guestToolsRunning: "En cours", guestToolsNotRunning: "Arrêtés",
    guestToolsExecutingScripts: "Scripts en cours", guestToolsNotInstalled: "Non installés" };
  const METRICS = { power_state: "État", health: "Santé", cpu_mhz: "CPU", vcpu: "vCPU",
    ram_configured: "RAM configurée", ram_active: "RAM active estimée", ram_host: "RAM sur hôte",
    uptime: "Uptime", tools: "VMware Tools", snapshots: "Snapshots", storage_committed: "Stockage engagé",
    storage_uncommitted: "Stockage non engagé", connection: "Connexion", maintenance: "Maintenance",
    cpu_used: "CPU", ram_percent: "RAM", ram_used: "RAM utilisée", ram_total: "RAM totale",
    accessible: "Accessible", capacity: "Capacité", free: "Libre", used: "Occupation",
    vms: "VM", vms_on: "VM allumées", hosts: "ESXi", hosts_connected: "ESXi connectés",
    datastores: "Datastores", storage_capacity: "Capacité totale", storage_free: "Libre total",
    net_rx: "Réception", net_tx: "Émission", power_w: "Puissance serveur", hardware_health: "Santé capteurs IPMI" };
  const missing = s => !s || s.state == null || ["unknown","unavailable","None","none",""].includes(String(s.state)) ||
    Boolean(s.attributes?.unit_of_measurement && !Number.isFinite(Number(s.state)));
  function metricLabel(metric, state) {
    if (metric.startsWith("net_rx:")) return "Réception";
    if (metric.startsWith("net_tx:")) return "Émission";
    const volume = metric.match(/^filesystem:(.*):(used|free)$/);
    if (volume) return `${volume[1]} · ${volume[2] === "used" ? "Occupation" : "Libre"}`;
    return METRICS[metric] || state?.attributes.metric_name || metric.replace(/^hardware:/, "");
  }
  function displayName(resource, config = {}) {
    return config.machine_names?.[resource.key]?.trim() || resource.attrs.dns_hostname || resource.name;
  }
  function temperatureLabel(key, state) {
    const raw = state.attributes.metric_name || metricLabel(key,state);
    const core=raw.match(/\bCore\s+(\d+)\b/i);
    if(core)return `Cœur ${core[1]}`;
    const pack=raw.match(/\bPackage\s*(?:id)?\s*(\d+)\b/i);
    if(pack)return `CPU · Package ${pack[1]}`;
    const acpi=raw.match(/acpitz[^·]*·\s*temp(\d+)/i);
    if(acpi)return `Zone ACPI ${acpi[1]}`;
    if(/\bTctl\b/i.test(raw))return "CPU · Tctl";
    if(/\bTdie\b/i.test(raw))return "CPU · Tdie";
    return raw;
  }
  const node = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = String(text);
    return el;
  };

  // Metadata, not generated entity names, drives membership. This follows vMotion.
  function rawInventory(states, vcenterId) {
    const resources = new Map();
    for (const state of Object.values(states)) {
      const a = state.attributes || {};
      const external = a.integration_domain === "infra_agent";
      if ((!external && a.integration_domain !== "infra_vcenter") || !a.metric_key ||
          (!external && vcenterId && a.vcenter_id !== vcenterId)) continue;
      const key = external ? `source:${a.source_uid}` : `${a.vcenter_id}:${a.resource_type}:${a.resource_id}`;
      if (!resources.has(key)) resources.set(key, { key, id: a.resource_id, vc: a.vcenter_id,
        kind: a.resource_type, name: a.resource_name, attrs: {}, metrics: {} });
      const r = resources.get(key);
      Object.assign(r.attrs, a);
      r.metrics[a.metric_key] = state;
    }
    return [...resources.values()].sort((a, b) => (a.name || "").localeCompare(b.name || "", "fr", { numeric: true }));
  }

  function canonicalMetric(key, state) {
    const a = state.attributes || {};
    if (a.metric_role) return a.metric_role;
    if (!key.startsWith("hardware:")) return key;
    if(key.endsWith(":health")) {
      const label=(a.metric_name||key).toLowerCase().replace(/system board\s*\d*/g,"").replace(/\s*·\s*santé$/,"").trim();
      return "health:"+label.replace(/[^a-z0-9]+/g,"_").replace(/^_|_$/g,"");
    }
    const unit = a.unit_of_measurement;
    const category = {"°C":"temperature", rpm:"fan", W:"component_power", V:"voltage", A:"current"}[unit];
    if (!category) return key;
    const label = (a.metric_name || key).toLowerCase().replace(/system board\s*\d*/g, "").trim();
    if (unit === "W" && /system level|system.*(?:power|pwr)|(?:power|pwr).*consumption|total.*power/.test(label) &&
      !/capacity|maximum|rated|budget|limit/.test(label)) return "power_w";
    if (category === "temperature" && /ambient|inlet|ambiant|entrée/.test(label)) return "temperature:ambient";
    return `${category}:${label.replace(/[^a-z0-9]+/g,"_").replace(/^_|_$/g,"")}`;
  }

  function mergeSources(target, sources, states, overrides = {}) {
    const candidates = new Map();
    for (const source of [target, ...sources]) {
      const counts={};
      for(const [key,state] of Object.entries(source.metrics)) {
        const role=canonicalMetric(key,state);counts[role]=(counts[role]||0)+1;
      }
      for (const [key, state] of Object.entries(source.metrics)) {
      const role = canonicalMetric(key, state);
      // If one source has several probes with the same role, retain each probe
      // instead of guessing that two physical sensors are duplicates.
      const canonical = counts[role]>1 ? `${role}:${key}` : role;
      if (!candidates.has(canonical)) candidates.set(canonical, []);
      const type = source.attrs.source_type || "vcenter";
      const hardware = /^(power_w|hardware_health|temperature:|fan:|voltage:|current:|component_power:|health:|state:)/.test(canonical);
      const priority = hardware ? {idrac:300,standalone:200,vcenter:100}[type] : {vcenter:300,standalone:200,idrac:100}[type];
      candidates.get(canonical).push({state, priority:priority || 0, source:source.attrs.source_uid || "vCenter"});
      }
    }
    for (const [key, id] of Object.entries(overrides)) {
      if (!states[id] || (key === "power_w" && states[id].attributes.unit_of_measurement !== "W")) continue;
      if (!candidates.has(key)) candidates.set(key, []);
      candidates.get(key).push({state:states[id],priority:1000,source:"Capteur choisi"});
    }
    const metrics = {};
    for (const [key, choices] of candidates) {
      const invalid=c=>missing(c.state)||(key==="power_w"&&Number(c.state.state)<0);
      choices.sort((a,b) => Number(invalid(a))-Number(invalid(b)) || b.priority-a.priority);
      const chosen = choices[0];
      metrics[key] = {...chosen.state, attributes:{...chosen.state.attributes, metric_key:key,
        data_source:chosen.source, source_entities:choices.map(c => c.state.entity_id)}};
    }
    return {...target, metrics, attrs:{...target.attrs, attached_sources:sources.map(s => s.name),
      power_methods:sources.map(s => s.attrs.power_method).filter(Boolean)}};
  }

  function inventory(states, vcenterId, config = {}) {
    const raw = rawInventory(states, vcenterId);
    const links = config.source_links || [];
    const linked = new Set();
    const output = raw.filter(r => r.kind !== "hardware").map(target => {
      const sources = raw.filter(source => source.kind === "hardware" &&
        links.filter(l => l.source === source.attrs.source_uid).length === 1 &&
        links.some(l => l.source === source.attrs.source_uid && l.target === target.key));
      sources.forEach(s => linked.add(s.key));
      const overrides = (config.metric_overrides || {})[target.key] || {};
      return sources.length || target.kind === "standalone" || Object.keys(overrides).length ?
        mergeSources(target,sources,states,overrides) : target;
    });
    return [...output, ...raw.filter(r => r.kind === "hardware" && !linked.has(r.key))];
  }

  function powerSummary(resources) {
    const machines = resources.filter(r => ["host","standalone"].includes(r.kind));
    const measured = machines.filter(r => !missing(r.metrics.power_w) &&
      r.metrics.power_w.attributes.unit_of_measurement === "W" && Number.isFinite(Number(r.metrics.power_w.state)) && Number(r.metrics.power_w.state) >= 0);
    return {watts:measured.length ? measured.reduce((sum,r) => sum+Number(r.metrics.power_w.state),0) : null,
      measured:measured.length,total:machines.length};
  }

  class InfrastructureCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.graphs = new Map();
      this.expanded = new Set();
      this.workerTabs = new Map();
      this.workerCoreCurves = new Set();
    }
    static getConfigElement() { return document.createElement("infra-vcenter-editor"); }
    connectedCallback() {
      if (this.config && this._hass) this.render();
    }
    setConfig(config = {}) {
      this.config = { title: "Infrastructure", hours_to_show: 24, ...config };
      this.hours = [6, 24, 168].includes(Number(config.hours_to_show)) ? Number(config.hours_to_show) : 24;
      this.signature = "";
      if (this._hass) this.render();
    }
    set hass(hass) {
      this._hass = hass;
      if (!this.config) return;
      const resources = inventory(hass.states, this.config.vcenter_id, this.config);
      const signature = JSON.stringify(resources);
      if (signature !== this.signature) {
        this.signature = signature;
        this.render(resources);
      }
      for (const graph of this.graphs.values()) graph.hass = hass;
    }
    getCardSize() { return 18; }
    getGridOptions() { return { columns: "full", rows: "auto" }; }

    format(state) {
      if (!state) return "Non remonté";
      if (missing(state)) return TEXT[state.state] || "Inconnu";
      const unit = state.attributes.unit_of_measurement;
      const number = Number(state.state);
      if (unit === "s" && Number.isFinite(number)) {
        const hours = Math.floor(number / 3600);
        return `${Math.floor(hours / 24)} j ${hours % 24} h`;
      }
      if (Number.isFinite(number) && state.state.trim() !== "")
        return `${number.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}${unit ? " " + unit : ""}`;
      return TEXT[state.state] || state.state;
    }
    info(entity) {
      if (entity) this.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId: entity }, bubbles: true, composed: true }));
    }
    color(percent) {
      if (percent >= 90) return "#ed6268";
      if (percent >= 80) return "#ed964c";
      if (percent >= 60) return "#dfb849";
      return "#44b884";
    }
    measure(resource, metric, label) {
      const state = resource.metrics[metric];
      const el = node("button", "measure");
      el.type = "button";
      el.append(node("span", "label", label || metricLabel(metric, state)), node("strong", "value", this.format(state)));
      el.disabled = !state;
      if (state?.attributes.data_source) el.title = `Source : ${state.attributes.data_source}`;
      el.onclick = () => this.info(state?.entity_id);
      if (state?.attributes.unit_of_measurement === "°C" && !missing(state)) {
        const ambient = /ambient|inlet|ambiant|entrée/i.test(state.attributes.metric_name || label || metric);
        const warn = Number(ambient ? this.config.ambient_warning ?? 35 : this.config.temperature_warning ?? 70);
        const critical = Number(ambient ? this.config.ambient_critical ?? 45 : this.config.temperature_critical ?? 85);
        const temperature = Number(state.state);
        el.querySelector(".value").style.color = temperature >= critical ? "#ed6268" : temperature >= warn ? "#ed964c" : "#44b884";
        el.title = `Repères visuels : orange ${warn} °C, rouge ${critical} °C. L’état matériel VMware reste la référence.`;
      }
      if (state?.attributes.unit_of_measurement === "%" && !missing(state)) {
        const meter = node("span", "meter");
        const fill = node("i");
        const percent = Math.max(0, Math.min(100, Number(state.state) || 0));
        fill.style.width = `${percent}%`;
        fill.style.background = this.color(percent);
        meter.append(fill);
        el.append(meter);
      }
      return el;
    }
    gauge(store) {
      const state = store.metrics.used;
      const percent = missing(state) ? null : Math.max(0, Math.min(100, Number(state.state)));
      const button = node("button", "gauge-button");
      button.onclick = () => this.info(state?.entity_id);
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 200 115");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", `${store.name} : ${percent === null ? "occupation inconnue" : percent.toFixed(1) + " % utilisés"}`);
      const point = (fraction, radius = 75) => [100 - radius * Math.cos(Math.PI * fraction), 98 - radius * Math.sin(Math.PI * fraction)];
      const path = (start, end, color) => {
        const p = document.createElementNS(svg.namespaceURI, "path");
        const a = point(start), b = point(end);
        p.setAttribute("d", `M${a[0]},${a[1]} A75,75 0 0 1 ${b[0]},${b[1]}`);
        p.setAttribute("fill", "none"); p.setAttribute("stroke", color); p.setAttribute("stroke-width", "18");
        svg.append(p);
      };
      if (percent === null) path(0, 1, "var(--divider-color)");
      else for (const [a, b, c] of [[0, .6, "#44b884"], [.6, .8, "#dfb849"], [.8, .9, "#ed964c"], [.9, 1, "#ed6268"]]) path(a, b, c);
      if (percent !== null) {
        const needle = document.createElementNS(svg.namespaceURI, "line");
        const a = point(percent / 100, 61), b = point(percent / 100, 88);
        for (const [key, val] of Object.entries({x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"var(--primary-text-color)","stroke-width":4,"stroke-linecap":"round"})) needle.setAttribute(key, val);
        svg.append(needle);
      }
      const label = document.createElementNS(svg.namespaceURI, "text");
      for (const [key, val] of Object.entries({x:100,y:94,"text-anchor":"middle",fill:"var(--primary-text-color)","font-size":30,"font-weight":650})) label.setAttribute(key, val);
      label.textContent = percent === null ? "-" : `${percent.toLocaleString("fr-FR", {maximumFractionDigits:1})} %`;
      svg.append(label); button.append(svg);
      const capacity = store.metrics.capacity, free = store.metrics.free;
      if (!missing(capacity) && !missing(free)) {
        const used = Number(capacity.state) - Number(free.state);
        button.append(node("span", "hint", `${used.toLocaleString("fr-FR", {maximumFractionDigits:1})} GiB utilisés`));
      }
      return button;
    }
    network(host, parent) {
      parent.append(node("h3", "", host.kind === "standalone" ? "Réseau · interfaces" : "Réseau · cartes physiques"));
      const nics = new Map((host.attrs.physical_nics || []).map(nic => [nic.device, nic]));
      for (const key of Object.keys(host.metrics)) if (/^net_(rx|tx):vmnic/.test(key)) {
        const name = key.split(":")[1];
        if (!nics.has(name)) nics.set(name, {device: name});
      }
      const grid = node("div", "nic-grid");
      for (const nic of [...nics.values()].sort((a, b) => a.device.localeCompare(b.device, "fr", {numeric: true}))) {
        const item = node("div", "subpanel nic");
        item.append(node("h4", "", nic.device), node("p", "hint", nic.speed_mbps ?
          `Lien ${nic.speed_mbps.toLocaleString("fr-FR")} Mbit/s${nic.full_duplex ? " · full duplex" : ""}` : "Vitesse de lien non remontée ou lien inactif"));
        const values = node("div", "metrics nic-values");
        for (const direction of ["rx", "tx"]) {
          const key = `net_${direction}:${nic.device}`;
          const measure = this.measure(host, key, direction === "rx" ? "↓ Réception" : "↑ Émission");
          const state = host.metrics[key];
          if (nic.speed_mbps && !missing(state)) {
            const percent = Number(state.state) / nic.speed_mbps * 100;
            const meter = node("span", "meter"); const fill = node("i");
            fill.style.width = `${Math.max(0,Math.min(100,percent))}%`; fill.style.background = this.color(percent);
            meter.append(fill); measure.append(node("span", "label", `${percent.toLocaleString("fr-FR", {maximumFractionDigits:1})} % du lien`), meter);
          }
          values.append(measure);
        }
        item.append(values); grid.append(item);
        const rx = host.metrics[`net_rx:${nic.device}`], tx = host.metrics[`net_tx:${nic.device}`];
        if (rx || tx) this.graph(item, host.key + ":nic:" + nic.device, `${nic.device} · Mbit/s`, [rx, tx]);
      }
      parent.append(grid);
      if (!nics.size || host.attrs.network_collection !== "ok") parent.append(node("p", "hint",
        `Compteurs réseau : ${host.attrs.network_collection || "en attente"}. Aucune valeur absente n’est remplacée par zéro.`));
      const switches = host.attrs.vswitches || [];
      if (switches.length) {
        const detail = node("details", "vm-detail"); detail.append(node("summary", "", "vSwitch standards · topologie et uplinks"));
        for (const sw of switches) {
          const uplinks = (sw.uplink_keys || []).map(key => [...nics.values()].find(n => n.key === key)?.device || key);
          detail.append(node("p", "hint", `${sw.name} · ${uplinks.join(", ") || "aucun uplink physique"} · MTU ${sw.mtu || "-"}`));
        }
        detail.append(node("p", "hint", "Les débits affichés sont ceux des cartes physiques. Ils ne mesurent pas tout le trafic interne d’un vSwitch entre VM du même hôte."));
        parent.append(detail);
      }
    }
    badge(state) {
      const bad = !state || ["red", "disconnected", "notResponding", "unavailable"].includes(state.state);
      return node("span", `badge ${bad ? "bad" : state.state === "yellow" ? "warn" : missing(state) || state.state === "gray" ? "muted" : ""}`, this.format(state));
    }
    async loadGraph(container, key, title, states, limitPercent = false) {
      const selected = states.filter(Boolean).filter(s => s.attributes.unit_of_measurement);
      if (!selected.length) {
        container.append(node("p", "hint", `${title} : aucune mesure disponible.`));
        return;
      }
      const entities = selected.slice(0, 8).map(s => ({ entity: s.entity_id,
        name: s.attributes.graph_name || (s.attributes.resource_type === "datastore" ? s.attributes.resource_name :
          metricLabel(s.attributes.metric_key, s)) }));
      const cacheKey = `${key}:${this.hours}:${JSON.stringify(entities)}`;
      this.activeGraphs.add(cacheKey);
      if (this.graphs.has(cacheKey)) {
        container.append(this.graphs.get(cacheKey));
        return;
      }
      try {
        const helpers = await window.loadCardHelpers();
        if (!container.isConnected || !this.activeGraphs.has(cacheKey)) return;
        const graph = helpers.createCardElement({ type: "history-graph", title,
          hours_to_show: this.hours, entities, ...(limitPercent ? { min_y_axis: 0, max_y_axis: 100 } : {}) });
        graph.hass = this._hass;
        this.graphs.set(cacheKey, graph);
        container.append(graph);
        if (selected.length > 8) container.append(node("p", "hint", "Graphique limité à 8 courbes ; toutes les mesures sont accessibles ci-dessus."));
      } catch (_) {
        if (container.isConnected) container.append(node("p", "hint", "Graphique non chargé. Les valeurs restent consultables en cliquant dessus."));
      }
    }
    graph(parent, key, title, states, percent = false) {
      const box = node("div", "graph");
      parent.append(box);
      // Delay until the rebuilt card is connected; HA then supplies native graphs.
      queueMicrotask(() => this.loadGraph(box, key, title, states, percent));
    }
    detailsList(resource) {
      const list = node("div", "metrics");
      for (const metric of Object.keys(resource.metrics)) {
        if (metric.endsWith(":health")) continue;
        list.append(this.measure(resource, metric));
      }
      return list;
    }
    vmPanel(vm, resources, onClose) {
      const panel = node("section", "vm-detail-panel");
      const header = node("div", "host-header");
      const heading = node("div");
      heading.append(node("div", "eyebrow", "MACHINE VIRTUELLE"), node("h3", "", vm.name));
      const actions = node("div", "badges");
      actions.append(this.badge(vm.metrics.power_state), this.badge(vm.metrics.health));
      const close = node("button", "close-detail", "Fermer ×");
      close.onclick = onClose; actions.append(close);
      header.append(heading, actions); panel.append(header);
      const overview = node("div", "vm-summary");
      const shown = new Set(["power_state", "health"]);
      const group = (title, keys) => {
        const box = node("div", "subpanel"); box.append(node("h4", "", title));
        const list = node("div", "fact-list");
        for (const key of keys) if (vm.metrics[key]) { list.append(this.measure(vm, key)); shown.add(key); }
        box.append(list); overview.append(box);
      };
      group("Calcul", ["cpu_mhz", "vcpu", "uptime"]);
      group("Mémoire", ["ram_host", "ram_active", "ram_configured"]);
      group("Stockage", ["storage_committed", "storage_uncommitted", "snapshots"]);
      panel.append(overview);
      const graphs = node("div", "graphs vm-graphs"); panel.append(graphs);
      this.graph(graphs, vm.key + ":cpu", "CPU · MHz", [vm.metrics.cpu_mhz]);
      this.graph(graphs, vm.key + ":ram", "RAM · GiB", [vm.metrics.ram_host, vm.metrics.ram_active]);
      if (vm.metrics.net_rx || vm.metrics.net_tx)
        this.graph(graphs, vm.key + ":network", "Réseau · Mbit/s", [vm.metrics.net_rx, vm.metrics.net_tx]);
      // Network values accompany the network graph rather than the general facts.
      const traffic = node("div", "traffic-inline");
      for (const key of ["net_rx", "net_tx"]) if (vm.metrics[key]) {
        traffic.append(this.measure(vm, key)); shown.add(key);
      }
      if (traffic.children.length) panel.append(traffic);
      const volumes = new Map();
      for (const key of Object.keys(vm.metrics)) {
        const match = key.match(/^filesystem:(.*):(used|free)$/);
        if (!match) continue;
        if (!volumes.has(match[1])) volumes.set(match[1], {});
        volumes.get(match[1])[match[2]] = key; shown.add(key);
      }
      if (volumes.size) {
        panel.append(node("h4", "volumes-title", "Volumes du système invité"));
        const grid = node("div", "volumes");
        for (const [path, metrics] of volumes) {
          const box = node("div", "subpanel"); box.append(node("h4", "volume-path", path));
          const list = node("div", "fact-list");
          for (const [metric, key] of Object.entries(metrics))
            list.append(this.measure(vm, key, metric === "used" ? "Occupation" : "Espace libre"));
          box.append(list); grid.append(box);
        }
        panel.append(grid);
      }
      const names = (vm.attrs.datastore_ids || []).map(id => resources.find(r => r.vc === vm.vc && r.kind === "datastore" && r.id === id)?.name || id);
      panel.append(node("p", "hint", `Datastores : ${names.join(", ") || "non remontés"}`));
      const technical = node("details", "technical"); technical.append(node("summary", "", "Informations système"));
      const remaining = node("div", "fact-list");
      for (const key of Object.keys(vm.metrics)) if (!shown.has(key) && !key.endsWith(":health")) remaining.append(this.measure(vm, key));
      const metadata = [vm.attrs.guest_os, vm.attrs.ip_address].filter(Boolean).join(" · ");
      if (metadata) technical.append(node("p", "hint", metadata));
      technical.append(remaining); panel.append(technical);
      return panel;
    }
    global(resource) {
      const direct=resource.attrs.api_type==="HostAgentGroup";
      const box = node("section", "panel global");
      box.append(node("div", "eyebrow", direct?"ESXi · ACCÈS DIRECT":"VCENTER · GLOBAL"), node("h2", "", "Vue d’ensemble"));
      box.append(node("p", "hint", direct ? "Supervision directe des hyperviseurs, sans vCenter." : `vSphere ${resource.attrs.version || "-"} · build ${resource.attrs.build || "-"} · API ${resource.attrs.api_version || "-"}${resource.attrs.scope==="selected_hosts"?" · périmètre ESXi sélectionnés":""}`));
      const metrics = node("div", "metrics");
      for (const key of ["hosts", "hosts_connected", "vms", "vms_on", "datastores", ...(direct?[]:["storage_capacity", "storage_free"])])
        metrics.append(this.measure(resource, key,direct&&key==="datastores"?"Datastores vus par hôte":undefined));
      box.append(metrics, node("p", "hint", direct ? "Les capacités des datastores ne sont pas additionnées entre accès directs : un même stockage peut être visible depuis plusieurs hôtes." : "Stockage global : chaque datastore est compté une seule fois, même s’il est partagé entre plusieurs hôtes."));
      if(resource.attrs.unavailable_endpoints?.length)box.append(node("p","hint",`Collecte partielle : ${resource.attrs.unavailable_endpoints.length} endpoint(s) indisponible(s).`));
      return box;
    }
    hardwareSection(host, parent) {
      const extra = Object.entries(host.metrics).filter(([key,state]) =>
        key !== "power_w" && key !== "hardware_health" && state.attributes.unit_of_measurement !== "°C" &&
        /^(hardware:|fan:|voltage:|current:|component_power:|health:|state:|power_state$)/.test(key));
      if (!extra.length && !host.metrics.power_w && !host.attrs.attached_sources?.length) return;
      const detail = node("details", "technical hardware-detail");
      detail.append(node("summary", "", "Matériel & alimentation · détails et sources"));
      const list = node("div", "metrics");
      for (const [key,state] of extra) list.append(this.measure(host,key,state.attributes.metric_name || metricLabel(key,state)));
      detail.append(list);
      if (host.attrs.attached_sources?.length) detail.append(node("p","hint",`Sources rattachées : ${host.attrs.attached_sources.join(", ")}`));
      if (host.attrs.attached_sources?.length && !host.metrics.power_w)
        detail.append(node("p","hint","Aucune puissance système exposée par les sources rattachées. Une mesure en watts d’une prise connectée peut être choisie dans l’éditeur."));
      if (host.metrics.power_w) {
        let loaded = false;
        detail.addEventListener("toggle", () => {
          if (detail.open && !loaded) { loaded = true; this.graph(detail,host.key+":power","Puissance serveur · W",[host.metrics.power_w]); }
        });
      }
      parent.append(detail);
    }
    standaloneVolumes(host, parent) {
      const volumes = new Map();
      for (const [key,state] of Object.entries(host.metrics)) {
        const match = key.match(/^filesystem:(.*):(used|free)$/);
        if (!match) continue;
        if (!volumes.has(match[1])) volumes.set(match[1],[]);
        volumes.get(match[1]).push([key,state]);
      }
      if (!volumes.size) return;
      parent.append(node("h3","","Disques & volumes"));
      const grid = node("div","volumes");
      for (const [path, metrics] of volumes) {
        const box = node("div","subpanel"); box.append(node("h4","volume-path",path));
        const list = node("div","fact-list");
        for (const [key] of metrics) list.append(this.measure(host,key,key.endsWith(":used")?"Occupation":"Espace libre"));
        box.append(list); grid.append(box);
      }
      parent.append(grid);
    }
    standalone(host) {
      const box=node("section","panel host-panel standalone-panel");
      const header=node("div","host-header");
      const title=node("div");
      title.append(node("div","eyebrow","SERVEUR STANDALONE"),node("h2","",displayName(host,this.config)),
        node("p","hint",`${host.attrs.model||"Linux"} · collecte MQTT`));
      const badges=node("div","badges");badges.append(this.badge(host.metrics.connection));
      if(host.metrics.hardware_health){const b=this.badge(host.metrics.hardware_health);b.textContent="IPMI · "+this.format(host.metrics.hardware_health);badges.append(b);}
      header.append(title,badges);box.append(header);
      const temperatures=Object.entries(host.metrics).filter(([,s])=>s.attributes.unit_of_measurement==="°C");
      const label=([key,state])=>state.attributes.metric_name||key;
      const packages=temperatures.filter(pair=>/package|\btctl\b|\btdie\b/i.test(label(pair)));
      const cores=temperatures.filter(pair=>/\bcore\s*\d+/i.test(label(pair)));
      const acpi=temperatures.filter(pair=>/acpitz|acpi/i.test(label(pair)));
      const primary=packages.length?packages:temperatures.filter(pair=>!missing(pair[1])).slice(0,1);
      const stats=node("div","metrics worker-stats");
      for(const key of ["cpu_used","ram_percent","ram_used","uptime",...(host.metrics.power_w?["power_w"]:[])]){
        const item=this.measure(host,key);
        if(key==="ram_used")item.append(node("span","label",`sur ${this.format(host.metrics.ram_total)}`));
        stats.append(item);
      }
      for(const [key,state]of primary){const item=this.measure(host,key,temperatureLabel(key,state));item.classList.add("worker-package");stats.append(item);}
      box.append(stats);
      const thermal=node("div","worker-thermal-strip");
      const shown=new Set(primary.map(([key])=>key));
      const chips=(heading,pairs,description)=>{
        const filtered=pairs.filter(([key])=>!shown.has(key));if(!filtered.length)return;
        const group=node("div","worker-probes");group.append(node("h4","",heading));
        const values=node("div","probe-chips");
        for(const [key,state]of filtered){shown.add(key);values.append(this.measure(host,key,temperatureLabel(key,state)));}
        group.append(values);if(description)group.append(node("p","hint",description));thermal.append(group);
      };
      chips("Cœurs CPU",cores);
      chips("Zones thermiques ACPI",acpi,"Sondes déclarées par le firmware ; emplacement physique non précisé.");
      chips("Autres sondes",temperatures);
      if(thermal.children.length)box.append(thermal);

      const nics=new Map((host.attrs.physical_nics||[]).map(n=>[n.device,n]));
      for(const key of Object.keys(host.metrics))if(/^net_(rx|tx):/.test(key)){
        const name=key.slice(key.indexOf(":")+1);if(!nics.has(name))nics.set(name,{device:name});
      }
      const interfaces=[...nics.values()].sort((a,b)=>a.device.localeCompare(b.device,"fr",{numeric:true}));
      const named=([key,state])=>({...state,attributes:{...state.attributes,graph_name:temperatureLabel(key,state)}});
      const networkStates=[];
      for(const nic of interfaces)for(const [direction,name]of [["rx","Réception"],["tx","Émission"]]){
        const state=host.metrics[`net_${direction}:${nic.device}`];
        if(state)networkStates.push({...state,attributes:{...state.attributes,graph_name:interfaces.length===1?name:`${nic.device} · ${name}`}});
      }
      const toolbar=node("div","worker-chart-toolbar");
      const tabs=node("div","periods worker-tabs");tabs.setAttribute("role","tablist");tabs.setAttribute("aria-label","Graphiques du serveur");
      const options=node("div","worker-chart-options");
      const charts=node("div","graphs host-charts worker-charts");
      const refresh=()=>{
        const thermalMode=this.workerTabs.get(host.key)==="temperatures";
        for(const button of tabs.children){const active=button.dataset.tab===(thermalMode?"temperatures":"usage");button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active));}
        charts.replaceChildren();options.replaceChildren();
        if(thermalMode){
          if(packages.length&&cores.length){
            const toggle=node("label","core-curves-toggle");const checkbox=node("input");checkbox.type="checkbox";checkbox.checked=this.workerCoreCurves.has(host.key);
            checkbox.onchange=()=>{if(checkbox.checked)this.workerCoreCurves.add(host.key);else this.workerCoreCurves.delete(host.key);refresh();};
            toggle.append(checkbox,document.createTextNode("Ajouter les cœurs à la courbe CPU"));options.append(toggle);
          }
          const cpu=packages.length?[...packages,...(this.workerCoreCurves.has(host.key)?cores:[])]:cores;
          this.graph(charts,host.key+":cpu-temperature","Températures CPU · °C",cpu.map(named));
          this.graph(charts,host.key+":acpi-temperature","Zones thermiques ACPI · °C",acpi.map(named));
        }else{
          this.graph(charts,host.key+":load","CPU et RAM · %",[host.metrics.cpu_used,host.metrics.ram_percent],true);
          this.graph(charts,host.key+":network","Réseau · Mbit/s",networkStates);
        }
      };
      for(const [key,text]of [["usage","Utilisation"],["temperatures","Températures"]]){
        const button=node("button","",text);button.type="button";button.dataset.tab=key;button.setAttribute("role","tab");
        button.onclick=()=>{this.workerTabs.set(host.key,key);refresh();};tabs.append(button);
      }
      toolbar.append(tabs,options);box.append(toolbar,charts);refresh();
      const bottom=node("div","worker-bottom");
      const network=node("div","subpanel worker-network");network.append(node("h3","","Réseau · interfaces"));
      for(const nic of interfaces){
        const row=node("div","worker-nic");const name=node("div");name.append(node("h4","",nic.device),node("p","hint",nic.speed_mbps?`Lien ${nic.speed_mbps.toLocaleString("fr-FR")} Mbit/s`:"Vitesse non remontée"));
        const traffic=node("div","worker-nic-traffic");
        for(const [direction,text]of [["rx","↓ Réception"],["tx","↑ Émission"]])traffic.append(this.measure(host,`net_${direction}:${nic.device}`,text));
        row.append(name,traffic);network.append(row);
      }
      if(!interfaces.length)network.append(node("p","hint","Aucune interface réseau remontée."));
      const storage=node("div","subpanel worker-storage");this.standaloneVolumes(host,storage);
      if(!storage.children.length)storage.append(node("h3","","Disques & volumes"),node("p","hint","Aucun volume remonté."));
      bottom.append(network,storage);box.append(bottom);this.hardwareSection(host,box);
      return box;
    }
    host(host, resources) {
      if(host.kind==="standalone")return this.standalone(host);
      const standalone = host.kind === "standalone";
      const vms = resources.filter(r => r.vc === host.vc && r.kind === "vm" && r.attrs.host_id === host.id);
      const stores = resources.filter(r => r.vc === host.vc && r.kind === "datastore" && (r.attrs.host_ids || []).includes(host.id));
      const box = node("section", "panel host-panel");
      const header = node("div", "host-header");
      const titles = node("div");
      const name=displayName(host,this.config);
      titles.append(node("div", "eyebrow", "HYPERVISEUR ESXI"), node("h2", "", name),
        node("p", "hint", `${host.attrs.model || "Serveur"} · ESXi ${host.attrs.esxi_version || "-"}${name!==host.name ? " · "+host.name : ""} · ${vms.length} VM rattachées`));
      const badges = node("div", "badges");
      badges.append(this.badge(host.metrics.connection));
      if (host.metrics.health) badges.append(this.badge(host.metrics.health));
      if (host.metrics.hardware_health) {
        const hardware = this.badge(host.metrics.hardware_health);
        hardware.textContent = "IPMI · " + this.format(host.metrics.hardware_health); badges.append(hardware);
      }
      if (host.metrics.maintenance?.state === "on") badges.append(node("span", "badge warn", "Maintenance"));
      if (host.attrs.partial_collection) badges.append(node("span", "badge warn", "Collecte partielle"));
      header.append(titles, badges);
      const stats = node("div", "metrics");
      for (const key of ["cpu_used", "ram_percent", "ram_used", "uptime", ...(standalone ? [] : ["vms_on"]), ...(host.metrics.power_w ? ["power_w"] : [])]) {
        const measure = this.measure(host, key);
        if (key === "ram_used") measure.append(node("span", "label", `sur ${this.format(host.metrics.ram_total)}`));
        if (key === "vms_on") measure.append(node("span", "label", `sur ${vms.length} VM rattachées`));
        stats.append(measure);
      }
      const temperatures = Object.entries(host.metrics).filter(([, s]) => s.attributes.unit_of_measurement === "°C");
      for (const [key, state] of temperatures)
        stats.append(this.measure(host, key, state.attributes.metric_name || key.replace(/^hardware:/, "")));
      box.append(header, stats);
      const history = node("div", "graphs host-charts");
      box.append(history);
      this.graph(history, host.key + ":load", "CPU et RAM · %", [host.metrics.cpu_used, host.metrics.ram_percent], true);
      if (temperatures.length) this.graph(history, host.key + ":temperatures", "Températures · °C", temperatures.map(([, s]) => s));
      else history.append(node("p", "hint", "Aucune température remontée par cet ESXi. La collecte IPMI des iDRAC 6 reste à raccorder."));

      this.network(host, box);
      if (standalone) {
        this.standaloneVolumes(host,box);
        this.hardwareSection(host,box);
        return box;
      }

      box.append(node("h3", "", `Datastores · ${stores.length}`));
      const disks = node("div", "datastores");
      for (const store of stores) {
        const ds = node("div", "subpanel");
        const title = node("div", "host-header");
        title.append(node("h4", "", store.name));
        const status = node("div", "badges");
        if (store.attrs.host_ids.length > 1) status.append(node("span", "hint", "Partagé"));
        const availability = store.metrics.accessible;
        status.append(node("span", `badge ${availability?.state === "off" ? "bad" : missing(availability) ? "muted" : ""}`,
          availability?.state === "on" ? "Accessible" : availability?.state === "off" ? "Hors ligne" : this.format(availability)));
        title.append(status);
        const values = node("div", "fact-list ds-values");
        for (const key of ["capacity", "free"]) values.append(this.measure(store, key));
        const usage = node("div", "datastore-usage"); usage.append(this.gauge(store), values);
        ds.append(title, usage);
        disks.append(ds);
      }
      box.append(disks);
      if (!stores.length) box.append(node("p", "hint", "Aucun datastore associé visible avec les droits actuels."));

      box.append(node("h3", "", `Machines virtuelles · ${vms.length}`));
      const scroll = node("div", "table-scroll");
      const table = node("table");
      const head = node("tr");
      for (const label of ["VM", "État", "CPU", "RAM sur hôte", "↓ Réseau", "↑ Réseau", "Stockage engagé", "Snapshots"])
        head.append(node("th", "", label));
      const thead = node("thead"); thead.append(head); table.append(thead);
      const body = node("tbody");
      const detailSlot = node("div", "vm-detail-slot");
      const toggles = new Map();
      let selected = vms.find(vm => this.expanded.has(vm.key));
      const showSelected = () => {
        detailSlot.replaceChildren();
        for (const [key, button] of toggles) {
          const active = selected?.key === key;
          button.setAttribute("aria-expanded", String(active));
          button.closest("tr").classList.toggle("selected", active);
        }
        if (selected) detailSlot.append(this.vmPanel(selected, resources, () => choose(selected)));
      };
      const choose = vm => {
        const opening = selected?.key !== vm.key;
        for (const item of vms) this.expanded.delete(item.key);
        selected = opening ? vm : undefined;
        if (selected) this.expanded.add(selected.key);
        showSelected();
      };
      for (const vm of vms) {
        const tr = node("tr");
        const name = node("td"); const btn = node("button", "vm-name", vm.name);
        btn.setAttribute("aria-label", `${vm.name} · afficher les détails`);
        btn.onclick = () => choose(vm); toggles.set(vm.key, btn); name.append(btn); tr.append(name);
        for (const metric of ["power_state", "cpu_mhz", "ram_host", "net_rx", "net_tx", "storage_committed", "snapshots"]) {
          const cell = node("td"); const action = node("button", "cell", missing(vm.metrics[metric]) ? "-" : this.format(vm.metrics[metric]));
          action.title = this.format(vm.metrics[metric]);
          if (metric === "power_state") action.classList.add(vm.metrics[metric]?.state === "poweredOn" ? "state-on" : "state-off");
          if (metric === "snapshots" && Number(vm.metrics[metric]?.state) > 0) action.classList.add("snapshot-present");
          action.onclick = () => this.info(vm.metrics[metric]?.entity_id); cell.append(action); tr.append(cell);
        }
        body.append(tr);
      }
      table.append(body); scroll.append(table); box.append(scroll);
      box.append(node("p", "hint table-hint", "Sélectionnez une VM pour afficher ses détails et graphiques."), detailSlot);
      showSelected();
      this.hardwareSection(host,box);
      return box;
    }

    render(resources = inventory(this._hass.states, this.config.vcenter_id, this.config)) {
      this.activeGraphs = new Set();
      const style = node("style");
      style.textContent = `
        :host{display:block;container-type:inline-size;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,system-ui)}
        *{box-sizing:border-box}h1,h2,h3,h4,p{margin:0}h1{font-size:28px;letter-spacing:-.7px}h2{font-size:23px;margin-top:4px}h3{font-size:17px;margin:26px 0 12px}h4{font-size:15px}
        .wrap{max-width:1560px;margin:auto;padding:12px 10px 28px}.top,.host-header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.top{margin:6px 0 18px}
        .eyebrow{font-size:11px;font-weight:750;letter-spacing:1.8px;color:var(--secondary-text-color)}.hint{color:var(--secondary-text-color);font-size:13px;line-height:1.6;margin-top:8px;overflow-wrap:anywhere}
        .panel{background:var(--ha-card-background,var(--card-background-color));border:1px solid var(--divider-color);border-radius:16px;padding:18px;margin-bottom:20px;box-shadow:var(--ha-card-box-shadow,none)}
        .global{border-top:3px solid #35b8d1}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-top:14px}
        button{font:inherit;color:inherit;cursor:pointer}.measure{position:relative;display:flex;flex-direction:column;gap:7px;text-align:left;min-width:0;padding:11px 12px;border-radius:9px;border:1px solid var(--divider-color);background:var(--secondary-background-color);overflow:hidden}
        button:disabled{cursor:default}.label{font-size:11px;color:var(--secondary-text-color);overflow-wrap:anywhere}.value{font-size:18px;font-weight:650;overflow-wrap:normal;font-variant-numeric:tabular-nums;line-height:1.35}.meter{height:3px;background:var(--divider-color);position:absolute;bottom:0;left:0;right:0}.meter i{display:block;height:100%}
        .badges{display:flex;flex-wrap:wrap;gap:8px}.badge{font-size:12px;background:#35b8d11c;color:var(--primary-text-color);border:1px solid #35b8d166;padding:6px 10px;border-radius:30px}.bad{border-color:#f16f71;background:#f16f7120}.warn{border-color:#e6b45b;background:#e6b45b20}.muted{border-color:var(--divider-color);background:var(--secondary-background-color)}
        .graphs{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;margin-top:16px}.graph{min-width:0;--ha-card-header-font-size:16px;--ha-card-header-font-weight:600;--ha-card-border-radius:10px}.host-charts>.graph{align-self:start}.datastores{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:10px}.subpanel{min-width:0;border:1px solid var(--divider-color);border-radius:10px;padding:12px}.subpanel .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
        .nic-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}.nic h4{font-size:14px}.nic>.hint{font-size:11px;margin-top:4px}.nic .measure{padding:9px 8px;gap:6px}.nic .value{font-size:15px;white-space:nowrap}.nic .label{font-size:10px}.nic>.graph{margin-top:10px}.nic-values{margin-top:10px}
        .datastore-usage{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px;align-items:center;margin-top:10px}.gauge-button{width:120px;border:0;background:transparent;padding:4px 0 0;text-align:center}.gauge-button svg{width:120px;display:block}.gauge-button .hint{display:block;font-size:10px;line-height:1.4;margin-top:2px}.datastores .host-header{gap:6px}.datastores h4{font-size:13px;overflow-wrap:anywhere}.datastores .badge{padding:3px 7px;font-size:10px}
        .fact-list{display:grid;gap:3px;margin-top:8px}.fact-list .measure{display:flex;flex-direction:row;align-items:center;justify-content:space-between;gap:10px;border:0;background:transparent;border-radius:5px;padding:8px 0}.fact-list .value{font-size:15px;white-space:nowrap}.fact-list .label{font-size:11px}.fact-list .meter{height:2px}.ds-values{margin-top:0}.ds-values .measure{padding:10px 0}.ds-values .value{font-size:15px}
        .vm-summary{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;margin-top:14px}.vm-summary h4,.volumes h4{font-size:13px}.vm-detail-panel{border:1px solid var(--divider-color);border-top:2px solid var(--primary-color);border-radius:12px;padding:16px;margin-top:16px}.vm-detail-panel h3{font-size:17px;margin:5px 0 0}.close-detail{background:transparent;border:1px solid var(--divider-color);border-radius:8px;padding:6px 10px;font-size:12px}.traffic-inline{display:flex;gap:12px;justify-content:flex-end;margin-top:8px}.traffic-inline .measure{flex-direction:row;gap:12px;align-items:center;background:transparent;border:0;padding:4px 0}.traffic-inline .value{font-size:13px}.technical{margin-top:12px;padding-top:12px;border-top:1px solid var(--divider-color)}.technical>.fact-list{grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:0 20px}.volumes-title{margin-top:18px;font-size:13px}.volumes{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr));gap:10px;margin-top:10px}.volume-path{font-family:monospace;overflow-wrap:anywhere}.table-hint{font-size:11px}.selected{background:color-mix(in srgb,var(--primary-color) 8%,transparent)}.state-on{color:#44b884}.state-off{color:var(--secondary-text-color)}.snapshot-present{color:#dfb849;font-weight:650}
        .table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px;color:inherit}th{text-align:left;color:var(--secondary-text-color);font-weight:500;white-space:nowrap}td,th{border-bottom:1px solid var(--divider-color);padding:13px 10px}td:first-child,th:first-child{padding-left:0}.cell,.vm-name{border:0;background:transparent;padding:0;text-align:left;white-space:nowrap}.vm-name{font-weight:650;color:var(--primary-color)}
        .vm-detail{border-bottom:1px solid var(--divider-color);padding:14px 0}summary{cursor:pointer;font-size:13px;font-weight:600}.periods{display:flex;gap:6px}.periods button{background:var(--secondary-background-color);border:1px solid var(--divider-color);border-radius:9px;padding:8px 12px}.periods button.active{background:var(--primary-color);color:var(--text-primary-color,#fff)}
        .worker-package{border-color:var(--primary-color)}.worker-package .value{font-size:22px}.worker-thermal-strip{display:flex;gap:24px;flex-wrap:wrap;margin-top:14px;padding:14px 0;border-bottom:1px solid var(--divider-color)}.worker-probes h4{font-size:12px;color:var(--secondary-text-color);font-weight:500;margin-bottom:8px}.probe-chips{display:flex;flex-wrap:wrap;gap:7px}.probe-chips .measure{flex-direction:row;align-items:center;gap:10px;padding:7px 10px;border-radius:7px}.probe-chips .value{font-size:14px;white-space:nowrap}.probe-chips .label{font-size:11px}.worker-probes>.hint{font-size:11px;margin-top:6px}
        .worker-chart-toolbar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-top:18px}.core-curves-toggle{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--secondary-text-color)}.worker-tabs button{font-size:12px;padding:7px 12px}.worker-bottom{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;margin-top:18px}.worker-bottom h3{font-size:14px;margin:0 0 12px}.worker-bottom .volumes{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));margin-top:0}.worker-bottom .volumes>.subpanel{border:0;padding:0}.worker-bottom .fact-list{margin-top:4px}.worker-nic{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--divider-color)}.worker-nic:last-child{border-bottom:0}.worker-nic h4{font-size:13px}.worker-nic .hint{font-size:11px;margin-top:4px}.worker-nic-traffic{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.worker-nic-traffic .measure{padding:7px 10px;min-width:110px}.worker-nic-traffic .value{font-size:14px}
        button:focus-visible,summary:focus-visible{outline:2px solid var(--primary-color);outline-offset:3px}
        @container(min-width:640px){.nic-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.host-charts,.vm-graphs{grid-template-columns:repeat(2,minmax(0,1fr))}.vm-summary{grid-template-columns:repeat(3,minmax(0,1fr))}.worker-bottom{grid-template-columns:repeat(2,minmax(0,1fr))}}
        @container(min-width:1080px){.nic-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.vm-graphs{grid-template-columns:repeat(3,minmax(0,1fr))}}
        @container(max-width:639px){.wrap{padding:10px 0}.panel{padding:14px;border-radius:12px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.value{font-size:17px}h1{font-size:24px}.vm-detail-panel{padding:12px}.datastore-usage{grid-template-columns:110px minmax(0,1fr);gap:8px}.gauge-button,.gauge-button svg{width:110px}.ds-values .value{font-size:14px}.traffic-inline{justify-content:flex-start;flex-wrap:wrap}.worker-nic{flex-wrap:wrap}.worker-nic-traffic{width:100%}.worker-nic-traffic .measure{min-width:0}}
      `;
      const wrap = node("div", "wrap");
      const top = node("div", "top"); const titles = node("div");
      titles.append(node("div", "eyebrow", "SUPERVISION"), node("h1", "", this.config.title));
      const periods = node("div", "periods");
      for (const [hours, label] of [[6, "6 h"], [24, "24 h"], [168, "7 j"]]) {
        const btn = node("button", hours === this.hours ? "active" : "", label);
        btn.setAttribute("aria-pressed", String(hours === this.hours));
        btn.onclick = () => { this.hours = hours; this.render(); };
        periods.append(btn);
      }
      top.append(titles, periods); wrap.append(top);
      if (!resources.length) wrap.append(node("p", "hint", "Aucune ressource compatible. Installer l’intégration Infrastructure vCenter 0.2.0, puis attendre une collecte."));
      for (const vc of resources.filter(r => r.kind === "vcenter")) wrap.append(this.global(vc));
      const power = powerSummary(resources);
      if (power.measured || resources.some(r=>r.kind==="standalone"||r.attrs.attached_sources?.length)) {
        const box = node("section","panel power-summary");
        box.append(node("div","eyebrow","PUISSANCE INFRASTRUCTURE"),
          node("h2","",power.watts === null ? "Puissance non mesurée" : `${power.watts.toLocaleString("fr-FR",{maximumFractionDigits:1})} W`),
          node("p","hint",`${power.measured} / ${power.total} machines mesurées${power.measured<power.total ? " · total partiel" : ""}. Une mesure par machine ; les VM et les alimentations individuelles ne sont pas additionnées.`));
        wrap.append(box);
      }
      const hosts = resources.filter(r => ["host","standalone"].includes(r.kind));
      for (const host of hosts) wrap.append(this.host(host, resources));
      const orphans = resources.filter(r => (r.kind === "vm" && !hosts.some(h => h.vc === r.vc && h.id === r.attrs.host_id)) ||
        (r.kind === "datastore" && !hosts.some(h => h.vc === r.vc && (r.attrs.host_ids || []).includes(h.id))));
      if (orphans.length) {
        const box = node("section", "panel"); box.append(node("h2", "", "Ressources sans hôte identifié"));
        for (const r of orphans) { box.append(node("h3", "", r.name), this.detailsList(r)); }
        wrap.append(box);
      }
      const hardware = resources.filter(r=>r.kind==="hardware");
      if (hardware.length) {
        const box=node("section","panel");box.append(node("h3","","Sources iDRAC à rattacher"));
        box.append(node("p","hint",hardware.map(r=>r.name).join(", ")+". Ouvrez l’éditeur de cette carte pour les associer aux machines. Ces sources ne sont pas comptées dans la puissance totale."));
        wrap.append(box);
      }
      wrap.append(node("p", "hint", "Graphiques : historique enregistré par Home Assistant. Cliquez sur une valeur pour ouvrir son détail. La RAM active des VM est une estimation ESXi."));
      this.shadowRoot.replaceChildren(style, wrap);
      // New graph keys are registered in the microtasks scheduled above.
      queueMicrotask(() => {
        for (const key of this.graphs.keys()) if (!this.activeGraphs.has(key)) this.graphs.delete(key);
      });
    }
  }
  class InfrastructureEditor extends HTMLElement {
    constructor(){super();this.attachShadow({mode:"open"});}
    setConfig(config){this.config={...config};this.render();}
    set hass(hass){
      this._hass=hass;
      const signature=JSON.stringify(rawInventory(hass.states).map(r=>[r.key,r.name,r.attrs.dns_hostname]));
      const powerSignature=Object.values(hass.states).filter(s=>s.attributes.unit_of_measurement==="W").map(s=>s.entity_id).join();
      if(signature+powerSignature!==this.signature){this.signature=signature+powerSignature;this.render();}
    }
    emit(patch){
      this.config={...this.config,...patch};this.render();
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this.config},bubbles:true,composed:true}));
    }
    select(options,value,onChange){
      const select=node("select");select.append(new Option("Choisir…",""));
      for(const [key,label] of options)select.append(new Option(label,key));
      select.value=value||"";select.onchange=()=>onChange(select.value);return select;
    }
    render(){
      if(!this.config)return;
      const raw=this._hass?rawInventory(this._hass.states):[];
      const targets=raw.filter(r=>["host","standalone"].includes(r.kind)).map(r=>[r.key,displayName(r,this.config)]);
      const sources=raw.filter(r=>r.kind==="hardware").map(r=>[r.attrs.source_uid,`${r.name} (${r.attrs.source_uid})`]);
      const power=this._hass?Object.values(this._hass.states).filter(s=>s.entity_id.startsWith("sensor.")&&s.attributes.unit_of_measurement==="W")
        .map(s=>[s.entity_id,`${s.attributes.friendly_name||s.entity_id} · ${s.entity_id}`]):[];
      const style=node("style");style.textContent=`:host{display:block;color:var(--primary-text-color);font-family:system-ui;font-size:14px}h3{margin:22px 0 10px;font-size:16px}p{line-height:1.5;color:var(--secondary-text-color)}.row{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin:10px 0}select,input{box-sizing:border-box;min-width:0;width:100%;background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);padding:10px;border-radius:6px}button{background:var(--primary-color);color:var(--text-primary-color);border:0;border-radius:6px;padding:8px 12px;cursor:pointer}.remove{background:transparent;color:var(--primary-text-color);border:1px solid var(--divider-color)}label{display:grid;gap:6px;font-size:12px}@media(max-width:500px){.row{grid-template-columns:1fr}.remove{justify-self:end}}`;
      const body=node("div");
      body.append(node("h3","","Noms d’affichage des machines"),node("p","","Le nom DNS de l’ESXi est utilisé lorsqu’il est disponible. Vous pouvez choisir ici un autre nom ; les rattachements et identifiants des capteurs sont conservés."));
      for(const resource of raw.filter(r=>["host","standalone"].includes(r.kind))){
        const row=node("label","",resource.name);const input=node("input");input.type="text";input.className="machine-name";input.dataset.machine=resource.key;
        input.placeholder=resource.attrs.dns_hostname||resource.name;input.value=this.config.machine_names?.[resource.key]||"";
        input.onchange=()=>{const names={...this.config.machine_names};if(input.value.trim())names[resource.key]=input.value.trim();else delete names[resource.key];this.emit({machine_names:names});};
        row.append(input);body.append(row);
      }
      body.append(node("h3","","Rattacher les sources matérielles"),node("p","","Choisissez l’iDRAC et la machine qu’il supervise. Les sources MQTT apparaîtront ici après le démarrage du collecteur. Le rattachement est enregistré dans la configuration de cette carte."));
      const links=this.config.source_links||[];
      for(const [index,link]of links.entries()){
        const row=node("div","row");
        const update=(key,value)=>this.emit({source_links:links.map((item,i)=>i===index?{...item,[key]:value}:item)});
        const source=node("label","","Source iDRAC");source.append(this.select(sources,link.source,v=>update("source",v)));
        const target=node("label","","Machine");target.append(this.select(targets,link.target,v=>update("target",v)));
        const remove=node("button","remove","Retirer");remove.onclick=()=>this.emit({source_links:links.filter((_,i)=>i!==index)});
        row.append(source,target,remove);body.append(row);
      }
      if(links.some(link=>link.source&&links.filter(l=>l.source===link.source).length>1))
        body.append(node("p","","Une source iDRAC ne peut être rattachée qu’à une machine. Supprimez le rattachement en double ; cette source restera en attente tant que le choix est ambigu."));
      const add=node("button","","Ajouter un rattachement");add.onclick=()=>this.emit({source_links:[...links,{source:"",target:""}]});body.append(add);
      body.append(node("h3","","Puissance : capteur choisi en priorité"),node("p","","Facultatif : choisissez un capteur en watts mesurant le serveur entier, par exemple une prise connectée. S’il est indisponible, la mesure iDRAC disponible sera utilisée."));
      const overrides=this.config.metric_overrides||{};
      for(const [target,label]of targets){
        const row=node("label","",label);
        row.append(this.select([["","Automatique"],...power],overrides[target]?.power_w,value=>{
          const updated={...overrides,[target]:{...overrides[target]}};
          if(value)updated[target].power_w=value;else delete updated[target].power_w;
          this.emit({metric_overrides:updated});
        }));body.append(row);
      }
      this.shadowRoot.replaceChildren(style,body);
    }
  }
  if(!customElements.get("infra-vcenter-editor"))customElements.define("infra-vcenter-editor",InfrastructureEditor);
  if (!customElements.get(TAG)) customElements.define(TAG, InfrastructureCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: TAG, name: "Infrastructure vCenter", description: "vCenter global, ESXi, VM, températures, datastores et historique." });
  // Export only the pure grouping helper for offline tests, no HA state is stored.
  if (typeof module !== "undefined" && module.exports) module.exports = { inventory, rawInventory, metricLabel, canonicalMetric, mergeSources, powerSummary, displayName, temperatureLabel };
})();
