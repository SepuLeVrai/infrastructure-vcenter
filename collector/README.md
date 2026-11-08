# Collecteur Linux / IPMI / MQTT

Le collecteur publie via MQTT Discovery : machine locale, Linux distants par SSH et iDRAC/BMC par IPMI. Une instance suffit si elle peut joindre les sources. Chaque instance doit avoir un agent_id distinct et stable.

## Installation Debian 13

Depuis le répertoire collector :

```bash
sudo bash install-debian.sh
sudo nano /etc/infra-agent/config.json
sudo nano /etc/infra-agent/secrets.env
```

L'installateur ajoute Python, Paho MQTT, lm-sensors, ipmitool et SSH, crée le compte système infra-agent et préserve la configuration existante. Il ne démarre pas le service.

Remplacer le broker et les BMC fictifs, supprimer les sources inutilisées. Une source linux lit la machine locale sans adresse IP. interfaces: [] choisit les interfaces physiques ; mounts sélectionne les volumes.

Mots de passe dans le fichier local secrets.env :

```ini
INFRA_MQTT_PASSWORD="remplacer-localement"
INFRA_BMC_NODE1_PASSWORD="remplacer-localement"
```

Dans JSON, password_env contient le **nom** de variable, jamais sa valeur. Les guillemets servent notamment aux espaces ; ils ne corrigent pas une référence erronée. Le fichier est lu par systemd et n'est pas un script shell.

## Assistant Linux distant

```bash
python3 configure.py
```

Il demande les adresses séparées par des points-virgules, la collecte locale et le broker, puis crée config.generated.json sans écraser de fichier. Sans interaction :

```bash
python3 configure.py --local --linux-hosts '192.0.2.31;192.0.2.32' \
  --mqtt-host mqtt.example.invalid --ssh-user monitor
```

Relire avant copie vers /etc/infra-agent/config.json. Préserver les agent_id, identifiants de sources et sources IPMI existants.

### Préparer SSH

Chaque serveur distant doit avoir python3, un compte dédié sans sudo autorisé par clé et accès en lecture à /proc, aux compteurs réseau et aux volumes choisis. lm-sensors est facultatif pour les températures. Aucun service distant n'est installé ; un programme de lecture est exécuté en mémoire.

Sur le collecteur :

```bash
sudo install -d -o infra-agent -g infra-agent -m 0700 /etc/infra-agent/ssh
sudo -u infra-agent ssh-keygen -t ed25519 -N '' -f /etc/infra-agent/ssh/id_ed25519
```

Installer la clé .pub dans ~monitor/.ssh/authorized_keys du serveur distant ; préférer les restrictions restrict et adresse source lorsque possible.

Obtenir et **vérifier l'empreinte de la clé hôte par un canal de confiance**, puis ajouter la clé à /etc/infra-agent/ssh/known_hosts. ssh-keyscan seul n'authentifie pas une clé. Tester :

```bash
sudo -u infra-agent ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/etc/infra-agent/ssh/known_hosts \
  -i /etc/infra-agent/ssh/id_ed25519 monitor@192.0.2.31 'python3 --version'
```

Source distante :

```json
{"id":"linux-node1","type":"ssh_linux","host":"192.0.2.31","username":"monitor","private_key_file":"/etc/infra-agent/ssh/id_ed25519","known_hosts_file":"/etc/infra-agent/ssh/known_hosts","mounts":["/"]}
```

Le nom remonte du serveur sauf si name est renseigné. Le temps de collecte s'ajoute à l'intervalle ; adapter le nombre de sources et la fréquence.

## iDRAC6 / IPMI

Activer IPMI sur le LAN, autoriser le compte IPMI au niveau USER et permettre UDP 623 depuis le collecteur. Les identifiants sont indépendants de VMware. Tester avec le vrai compte, sans mot de passe dans la commande :

```bash
read -rp 'Utilisateur IPMI : ' infra_bmc_user
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER mc info
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER sensor
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER dcmi power reading
```

cipher_suite: 3 vise iDRAC6 ; choisir le profil supporté par votre matériel (17 possible sur BMC récents). DCMI n'est pas universel : son absence laisse les autres sondes utilisables. Puissance = lecture instantanée DCMI ou sonde système reconnue, jamais addition des alimentations.

## Vérifier et démarrer

```bash
sudo /usr/bin/python3 /opt/infra-agent/bridge.py /etc/infra-agent/config.json --check
sudo systemd-run --wait --pipe --collect \
  --property=User=infra-agent --property=Group=infra-agent \
  --property=EnvironmentFile=/etc/infra-agent/secrets.env \
  --working-directory=/opt/infra-agent \
  /usr/bin/python3 /opt/infra-agent/bridge.py /etc/infra-agent/config.json --once
```

--check valide sans connexion. --once lit sans publier sur MQTT ; le premier CPU/réseau local peut être null car deux observations sont nécessaires. Retirer les informations privées avant de partager une sortie.

```bash
sudo systemctl enable --now infra-agent
systemctl is-enabled infra-agent
systemctl is-active infra-agent
sudo journalctl -u infra-agent -n 60 --no-pager
```

enable active le démarrage au reboot. MQTT Discovery doit être activé dans Home Assistant. Le broker doit autoriser les publications homeassistant/sensor/infra_* et infrastructure/<agent_id>/..., et l'abonnement au statut Home Assistant. Les topics des autres appareils ne sont pas modifiés.

Après modification : sudo systemctl restart infra-agent. Pour mettre à jour, relancer l'installateur puis redémarrer. Les configurations sont conservées.

Les sources en panne deviennent indisponibles. Les états ne sont pas conservés comme mesures fraîches après redémarrage. mqtt.tls: true utilise la validation système du certificat ; adapter également le port du broker (souvent 8883).
