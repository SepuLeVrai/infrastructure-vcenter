# Vue Infrastructure

Copier www/infra-vcenter vers /config/www/infra-vcenter. Dans les ressources du tableau de bord (profil en mode avancÃ© si nÃ©cessaire), ajouter **Module JavaScript** :

`/local/infra-vcenter/infrastructure-card.js?v=0.4.0`

Actualiser le navigateur. Aucun plugin graphique supplÃ©mentaire requis.

## CrÃ©er la vue

Ajouter une vue **Panneau (carte unique)**, puis une carte manuelle :

```yaml
type: custom:infra-vcenter-overview
hours_to_show: 24
```

Le type personnalisÃ© appartient Ã  la **carte**, pas Ã  la vue. Dans la configuration complÃ¨te d'un tableau de bord, ajouter cet Ã©lÃ©ment Ã  la liste views :

```yaml
title: Infrastructure
path: infrastructure
icon: mdi:lan
type: panel
cards:
  - type: custom:infra-vcenter-overview
    hours_to_show: 24
```

Ne remplacer pas tout le tableau de bord par cet extrait.

## Noms, rattachements et puissance

**Modifier le tableau de bord â†’ Modifier la carte** ouvre l'Ã©diteur de la carte : noms personnalisÃ©s, rattachements IPMI et capteurs de puissance. La fenÃªtre **Configuration de la vue** ne rÃ¨gle pas ces paramÃ¨tres.

Rattacher chaque iDRAC/BMC MQTT Ã  son serveur. Une source matÃ©rielle ne doit appartenir qu'Ã  une machine. VMware fournit les usages CPU/RAM, IPMI est prioritaire pour le matÃ©riel. Une mÃªme mesure reconnue n'est affichÃ©e qu'une fois ; des sondes non identifiÃ©es comme Ã©quivalentes restent distinctes. Les entitÃ©s et historiques d'origine sont conservÃ©s.

Le nom DNS ESXi est affichÃ© automatiquement ; un nom personnalisÃ© prend la prioritÃ©. L'IP reste disponible comme contexte.

Pour une prise, sÃ©lectionner le capteur de **puissance instantanÃ©e en W**, pas l'Ã©nergie en kWh. Le total additionne une mesure par machine et indique une couverture partielle si nÃ©cessaire. Une prise alimentant plusieurs serveurs ne doit pas Ãªtre rattachÃ©e Ã  chacun.

## Structure YAML fictive

L'Ã©diteur choisit les identifiants rÃ©els ; les clÃ©s ci-dessous ne sont pas des IP :

```yaml
type: custom:infra-vcenter-overview
hours_to_show: 24
machine_names:
  "vc-example:host:host-1": "ESXi node 1"
source_links:
  - source: "example:bmc-node1"
    target: "vc-example:host:host-1"
metric_overrides:
  "source:example:linux-node1":
    power_w: sensor.example_plug_power
```

En mode direct les clÃ©s comportent l'identitÃ© ESXi. Utiliser l'Ã©diteur Ã©vite les erreurs.

Les graphiques dÃ©pendent de Recorder. Autoriser les entitÃ©s si vous utilisez une liste d'inclusion. Aucun historique n'est importÃ© de vCenter. Les boutons 6 h / 24 h / 7 j ne crÃ©ent pas de donnÃ©es antÃ©rieures Ã  l'installation.
