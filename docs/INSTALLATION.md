# Installation Home Assistant

Home Assistant doit permettre les intégrations personnalisées et l'accès à son dossier /config. Sur HAOS, Samba ou un éditeur de fichiers permettent la copie. Home Assistant installe lui-même la dépendance Python VMware du manifeste.

1. Télécharger le code du dépôt ou l'archive complète produite par tools/build_release.py.
2. Copier custom_components/infra_vcenter vers /config/custom_components/infra_vcenter. manifest.json doit être directement dans ce dossier.
3. Redémarrer Home Assistant.
4. Dans **Paramètres → Appareils et services → Ajouter une intégration**, rechercher **Infrastructure vCenter**.
5. Suivre [la configuration VMware](VMWARE.md).

Pour Linux/IPMI seuls, l'intégration VMware n'est pas nécessaire : installer le collecteur avec MQTT natif, puis la carte. Le collecteur s'installe sur Debian, pas dans HAOS.

Suivre [l'installation de la vue](../dashboards/INSTALLATION-VUE.md). L'installation est manuelle ; cette version n'est pas distribuée comme dépôt HACS.

Avant une mise à jour, sauvegarder Home Assistant et le YAML de la carte. Remplacer le code et la ressource JS, redémarrer Home Assistant, augmenter le paramètre ?v= de la ressource et actualiser le navigateur. Conserver les entrées d'intégration et les identifiants du collecteur.

Les comptes VMware doivent avoir un rôle en lecture seule propagé sur l'inventaire concerné. Protéger les sauvegardes Home Assistant contenant leurs identifiants.
