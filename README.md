# Infrastructure vCenter

Vue unifiée pour Home Assistant. Elle réunit les VM, hyperviseurs ESXi, Linux, sondes IPMI et mesures de puissance. Le projet fournit une intégration VMware en lecture seule, une carte de supervision et un collecteur Linux/MQTT en service système. Licence [MIT](LICENSE).

## Choisir son installation

| Besoin | Configuration |
| --- | --- |
| vCenter et tous ses ESXi | Adresse vCenter ; liste ESXi vide |
| Certains ESXi de vCenter | Adresse vCenter et liste ESXi séparée par `;` |
| ESXi sans vCenter | vCenter vide, liste ESXi séparée par `;` |
| Linux local | Collecteur sur ce serveur, source `linux` |
| Plusieurs Linux distants | Collecteur central, adresses et accès SSH par clé |
| iDRAC / BMC | Source IPMI sur le collecteur, puis rattachement dans la carte |
| Prise avec mesure de puissance | Entité Home Assistant en watts sélectionnée dans la carte |

Adresses fictives : `192.0.2.10` (vCenter), `192.0.2.11;192.0.2.12` (ESXi), `192.0.2.31;192.0.2.32` (Linux). Remplacer les exemples avant utilisation. Aucune découverte de votre réseau n'est lancée automatiquement.

## Démarrage

1. Installer l'intégration depuis un dépôt personnalisé dans le Marketplace ou HACS, ou copier l'archive par Samba. [Guide HAOS et mise à jour](docs/INSTALLATION.md).
2. Pour une première installation, ajouter **Infrastructure vCenter** dans les intégrations. [Paramétrage VMware](docs/VMWARE.md).
3. Créer la vue. Le module JavaScript est fourni avec l'intégration. [Guide de la carte](dashboards/INSTALLATION-VUE.md).
4. Pour Linux/IPMI, installer le [collecteur Debian/MQTT](collector/README.md). MQTT fonctionne également sans intégration VMware.

## Données disponibles

- vCenter : inventaire et stockage partagé compté une seule fois.
- ESXi : connexion, santé, maintenance, CPU, RAM, uptime, VM, datastores, sondes exposées, débit des cartes physiques et topologie des vSwitch standards.
- VM : état, santé, CPU en MHz, RAM configurée/active estimée/sur hôte, réseau, stockage engagé, snapshots, VMware Tools et volumes invités.
- Linux : CPU, RAM, uptime, interfaces, volumes sélectionnés et sondes lm-sensors.
- IPMI : températures, ventilateurs, tensions, états et puissance système si exposée.

Les données absentes restent inconnues. La RAM active VMware est une estimation. Aucun débit de vSwitch n'est déduit des uplinks. Les watts d'un package CPU ou la capacité d'une alimentation ne représentent pas la consommation du serveur.

## État et compatibilité

Version **0.4.1**, pour Home Assistant Core 2026.6 ou ultérieur. Le chemin vCenter 6.7, le collecteur Debian 13 local et les lectures IPMI iDRAC6 ont été utilisés sur matériel réel pendant le développement. Les modes ESXi direct et SSH sont couverts par des tests simulés. Leur validation sur installation réelle reste à effectuer. [Téléchargements](https://github.com/SepuLeVrai/infrastructure-vcenter/releases/tag/0.4.1).

Les graphiques utilisent l'historique Home Assistant et se remplissent après installation. Aucun plugin graphique supplémentaire n'est nécessaire. MQTT doit être installé et intégré à Home Assistant pour le collecteur ; un broker existant convient.

## Maintenance

[Développement et tests](docs/DEVELOPMENT.md) · [Dépannage](docs/TROUBLESHOOTING.md) · [Changements](CHANGELOG.md)

Ne pas versionner configurations d'exploitation, mots de passe, clés SSH ou captures réelles. Les exemples et tests utilisent des données fictives. Conserver les identifiants existants lors d'une mise à jour pour préserver les entités et l'historique.
