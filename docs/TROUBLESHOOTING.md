# Dépannage

| Symptôme | Contrôle |
| --- | --- |
| Intégration absente | Chemin /config/custom_components/infra_vcenter/manifest.json puis redémarrage |
| Nom introuvable | DNS vu de Home Assistant ; tester l'IP |
| Erreur TLS | Nom du certificat et autorité reconnue ; test temporaire sans vérification |
| VMware refuse le compte | SSO pour vCenter, local pour ESXi direct, permissions propagées |
| ESXi sélectionné absent | Nom inventorié, DNS ou IP VMkernel visible par le compte |
| Carte inconnue | Ressource Module JavaScript, URL, cache et ?v= |
| Pas d'éditeur visuel | Modifier la carte et pas la vue ; actualiser le JS |
| Historique vide | Attendre des mesures et vérifier Recorder |
| Missing password secret | password_env référence une variable non vide chargée par systemd |
| IPMI session refusée | Vrai compte IPMI, mot de passe, IPMI LAN, UDP 623, privilège et cipher |
| SSH échoue | Tester sous infra-agent, vérifier clé, known_hosts et Python distant |
| Puissance absente | Sonde système réelle nécessaire ; sinon choisir une prise en W |
| Premier CPU/réseau Linux null | Attendre deux observations |

Journaux VMware : **Paramètres → Système → Journaux**, recherche infra_vcenter ou VCENTER_CONNECT. Collecteur : sudo journalctl -u infra-agent -n 60 --no-pager.

--once teste les lectures, pas MQTT. Contrôler ensuite le service et les appareils MQTT.

Avant un ticket public, retirer domaines, IP réelles, identifiants, numéros de série et chemins personnels. Ne joindre jamais secrets.env, config.json, clé privée ou sauvegarde Home Assistant.
