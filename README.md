# Infrastructure vCenter

Vue unifiÃ©e pour Home Assistant : VM, hyperviseurs ESXi, Linux, sondes IPMI et puissance Ã©lectrique. IntÃ©gration VMware en lecture seule, carte locale sans dÃ©pendance HACS et collecteur Linux/MQTT en service systÃ¨me. Licence [MIT](LICENSE).

## Choisir son installation

| Besoin | Configuration |
| --- | --- |
| vCenter et tous ses ESXi | Adresse vCenter ; liste ESXi vide |
| Certains ESXi de vCenter | Adresse vCenter et liste ESXi sÃ©parÃ©e par `;` |
| ESXi sans vCenter | vCenter vide, liste ESXi sÃ©parÃ©e par `;` |
| Linux local | Collecteur sur ce serveur, source `linux` |
| Plusieurs Linux distants | Collecteur central, adresses et accÃ¨s SSH par clÃ© |
| iDRAC / BMC | Source IPMI sur le collecteur, puis rattachement dans la carte |
| Prise avec mesure de puissance | EntitÃ© Home Assistant en watts sÃ©lectionnÃ©e dans la carte |

Adresses fictives : `192.0.2.10` (vCenter), `192.0.2.11;192.0.2.12` (ESXi), `192.0.2.31;192.0.2.32` (Linux). Remplacer les exemples avant utilisation. Aucune dÃ©couverte de votre rÃ©seau n'est lancÃ©e automatiquement.

## DÃ©marrage

1. [Installer l'intÃ©gration](docs/INSTALLATION.md) et redÃ©marrer Home Assistant.
2. Ajouter **Infrastructure vCenter** dans les intÃ©grations. [ParamÃ©trage VMware](docs/VMWARE.md).
3. Installer la ressource JavaScript et [crÃ©er la vue](dashboards/INSTALLATION-VUE.md).
4. Pour Linux/IPMI, installer le [collecteur Debian/MQTT](collector/README.md). MQTT fonctionne Ã©galement sans intÃ©gration VMware.

## DonnÃ©es disponibles

- vCenter : inventaire et stockage partagÃ© comptÃ© une seule fois.
- ESXi : connexion, santÃ©, maintenance, CPU, RAM, uptime, VM, datastores, sondes exposÃ©es, dÃ©bit des cartes physiques et topologie des vSwitch standards.
- VM : Ã©tat, santÃ©, CPU en MHz, RAM configurÃ©e/active estimÃ©e/sur hÃ´te, rÃ©seau, stockage engagÃ©, snapshots, VMware Tools et volumes invitÃ©s.
- Linux : CPU, RAM, uptime, interfaces, volumes sÃ©lectionnÃ©s et sondes lm-sensors.
- IPMI : tempÃ©ratures, ventilateurs, tensions, Ã©tats et puissance systÃ¨me si exposÃ©e.

Les donnÃ©es absentes restent inconnues. La RAM active VMware est une estimation. Aucun dÃ©bit de vSwitch n'est dÃ©duit des uplinks. Les watts d'un package CPU ou la capacitÃ© d'une alimentation ne reprÃ©sentent pas la consommation du serveur.

## Ã‰tat et compatibilitÃ©

Version **0.4.0**, expÃ©rimentale. Le chemin vCenter 6.7, le collecteur Debian 13 local et les lectures IPMI iDRAC6 ont Ã©tÃ© utilisÃ©s sur matÃ©riel rÃ©el pendant le dÃ©veloppement. Les nouveaux modes ESXi direct et SSH sont couverts par des tests simulÃ©s ; leur validation sur installation rÃ©elle reste Ã  effectuer. La configuration Home Assistant complÃ¨te doit Ã©galement Ãªtre vÃ©rifiÃ©e aprÃ¨s installation de cette version.

Les graphiques utilisent l'historique Home Assistant et se remplissent aprÃ¨s installation. Aucun plugin graphique supplÃ©mentaire n'est nÃ©cessaire. MQTT doit Ãªtre installÃ© et intÃ©grÃ© Ã  Home Assistant pour le collecteur ; un broker existant convient.

## Maintenance

[DÃ©veloppement et tests](docs/DEVELOPMENT.md) Â· [DÃ©pannage](docs/TROUBLESHOOTING.md) Â· [Changements](CHANGELOG.md)

Ne pas versionner configurations d'exploitation, mots de passe, clÃ©s SSH ou captures rÃ©elles. Les exemples et tests utilisent des donnÃ©es fictives. Conserver les identifiants existants lors d'une mise Ã  jour pour prÃ©server les entitÃ©s et l'historique.
