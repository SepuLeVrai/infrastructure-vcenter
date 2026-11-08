# DÃ©pannage

| SymptÃ´me | ContrÃ´le |
| --- | --- |
| IntÃ©gration absente | Chemin /config/custom_components/infra_vcenter/manifest.json puis redÃ©marrage |
| Nom introuvable | DNS vu de Home Assistant ; tester l'IP |
| Erreur TLS | Nom du certificat et autoritÃ© reconnue ; test temporaire sans vÃ©rification |
| VMware refuse le compte | SSO pour vCenter, local pour ESXi direct, permissions propagÃ©es |
| ESXi sÃ©lectionnÃ© absent | Nom inventoriÃ©, DNS ou IP VMkernel visible par le compte |
| Carte inconnue | Ressource Module JavaScript, URL, cache et ?v= |
| Pas d'Ã©diteur visuel | Modifier la carte et pas la vue ; actualiser le JS |
| Historique vide | Attendre des mesures et vÃ©rifier Recorder |
| Missing password secret | password_env rÃ©fÃ©rence une variable non vide chargÃ©e par systemd |
| IPMI session refusÃ©e | Vrai compte IPMI, mot de passe, IPMI LAN, UDP 623, privilÃ¨ge et cipher |
| SSH Ã©choue | Tester sous infra-agent, vÃ©rifier clÃ©, known_hosts et Python distant |
| Puissance absente | Sonde systÃ¨me rÃ©elle nÃ©cessaire ; sinon choisir une prise en W |
| Premier CPU/rÃ©seau Linux null | Attendre deux observations |

Journaux VMware : **ParamÃ¨tres â†’ SystÃ¨me â†’ Journaux**, recherche infra_vcenter ou VCENTER_CONNECT. Collecteur : sudo journalctl -u infra-agent -n 60 --no-pager.

--once teste les lectures, pas MQTT. ContrÃ´ler ensuite le service et les appareils MQTT.

Avant un ticket public, retirer domaines, IP rÃ©elles, identifiants, numÃ©ros de sÃ©rie et chemins personnels. Ne joindre jamais secrets.env, config.json, clÃ© privÃ©e ou sauvegarde Home Assistant.
