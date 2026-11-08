# Installation Home Assistant

Home Assistant doit permettre les intÃ©grations personnalisÃ©es et l'accÃ¨s Ã  son dossier /config. Sur HAOS, Samba ou un Ã©diteur de fichiers permettent la copie. Home Assistant installe lui-mÃªme la dÃ©pendance Python VMware du manifeste.

1. TÃ©lÃ©charger le code du dÃ©pÃ´t ou l'archive complÃ¨te produite par tools/build_release.py.
2. Copier custom_components/infra_vcenter vers /config/custom_components/infra_vcenter. manifest.json doit Ãªtre directement dans ce dossier.
3. RedÃ©marrer Home Assistant.
4. Dans **ParamÃ¨tres â†’ Appareils et services â†’ Ajouter une intÃ©gration**, rechercher **Infrastructure vCenter**.
5. Suivre [la configuration VMware](VMWARE.md).

Pour Linux/IPMI seuls, l'intÃ©gration VMware n'est pas nÃ©cessaire : installer le collecteur avec MQTT natif, puis la carte. Le collecteur s'installe sur Debian, pas dans HAOS.

Suivre [l'installation de la vue](../dashboards/INSTALLATION-VUE.md). L'installation est manuelle ; cette version n'est pas distribuÃ©e comme dÃ©pÃ´t HACS.

Avant une mise Ã  jour, sauvegarder Home Assistant et le YAML de la carte. Remplacer le code et la ressource JS, redÃ©marrer Home Assistant, augmenter le paramÃ¨tre ?v= de la ressource et actualiser le navigateur. Conserver les entrÃ©es d'intÃ©gration et les identifiants du collecteur.

Les comptes VMware doivent avoir un rÃ´le en lecture seule propagÃ© sur l'inventaire concernÃ©. ProtÃ©ger les sauvegardes Home Assistant contenant leurs identifiants.
