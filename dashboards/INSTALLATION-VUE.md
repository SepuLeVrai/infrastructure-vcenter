# Vue Infrastructure

Avec l'intégration VMware 0.4.1 et les ressources gérées dans l'interface, la ressource est déclarée au démarrage. Avec des ressources déclarées en YAML, utiliser cette URL comme **Module JavaScript** dans l'entrée existante.

`/infra-vcenter/infrastructure-card.js?v=0.4.1`

Pour une installation MQTT seule, copier `www/infra-vcenter` vers `/config/www/infra-vcenter` depuis l'archive interface. Déclarer le module `/local/infra-vcenter/infrastructure-card.js?v=0.4.1`.

Actualiser le navigateur. Aucun plugin graphique supplémentaire requis.

## Créer la vue

Ajouter une vue **Panneau (carte unique)**, puis une carte manuelle :

```yaml
type: custom:infra-vcenter-overview
hours_to_show: 24
```

Le type personnalisé appartient à la **carte**, pas à la vue. Dans la configuration complète d'un tableau de bord, ajouter cet élément à la liste views :

```yaml
title: Infrastructure
path: infrastructure
icon: mdi:lan
type: panel
cards:
  - type: custom:infra-vcenter-overview
    hours_to_show: 24
```

Pour une vue déjà configurée, conserver son YAML.

## Noms, rattachements et puissance

**Modifier le tableau de bord → Modifier la carte** ouvre l'éditeur de la carte : noms personnalisés, rattachements IPMI et capteurs de puissance. La fenêtre **Configuration de la vue** ne règle pas ces paramètres.

Rattacher chaque iDRAC/BMC MQTT à son serveur. Une source matérielle ne doit appartenir qu'à une machine. VMware fournit les usages CPU/RAM, IPMI est prioritaire pour le matériel. Une même mesure reconnue n'est affichée qu'une fois ; des sondes non identifiées comme équivalentes restent distinctes. Les entités et historiques d'origine sont conservés.

Le nom DNS ESXi est affiché automatiquement ; un nom personnalisé prend la priorité. L'IP reste disponible comme contexte.

Pour une prise, sélectionner le capteur de **puissance instantanée en W**, pas l'énergie en kWh. Le total additionne une mesure par machine et indique une couverture partielle si nécessaire. Une prise alimentant plusieurs serveurs ne doit pas être rattachée à chacun.

## Structure YAML fictive

L'éditeur choisit les identifiants réels ; les clés ci-dessous ne sont pas des IP :

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

En mode direct les clés comportent l'identité ESXi. Utiliser l'éditeur évite les erreurs.

Les graphiques dépendent de Recorder. Autoriser les entités si vous utilisez une liste d'inclusion. Aucun historique n'est importé de vCenter. Les boutons 6 h / 24 h / 7 j ne créent pas de données antérieures à l'installation.
