# Collecteur Linux / IPMI / MQTT

Le collecteur publie via MQTT Discovery : machine locale, Linux distants par SSH et iDRAC/BMC par IPMI. Une instance suffit si elle peut joindre les sources. Chaque instance doit avoir un agent_id distinct et stable.

## Installation Debian 13

Depuis le rÃ©pertoire collector :

```bash
sudo bash install-debian.sh
sudo nano /etc/infra-agent/config.json
sudo nano /etc/infra-agent/secrets.env
```

L'installateur ajoute Python, Paho MQTT, lm-sensors, ipmitool et SSH, crÃ©e le compte systÃ¨me infra-agent et prÃ©serve la configuration existante. Il ne dÃ©marre pas le service.

Remplacer le broker et les BMC fictifs, supprimer les sources inutilisÃ©es. Une source linux lit la machine locale sans adresse IP. interfaces: [] choisit les interfaces physiques ; mounts sÃ©lectionne les volumes.

Mots de passe dans le fichier local secrets.env :

```ini
INFRA_MQTT_PASSWORD="remplacer-localement"
INFRA_BMC_NODE1_PASSWORD="remplacer-localement"
```

Dans JSON, password_env contient le **nom** de variable, jamais sa valeur. Les guillemets servent notamment aux espaces ; ils ne corrigent pas une rÃ©fÃ©rence erronÃ©e. Le fichier est lu par systemd et n'est pas un script shell.

## Assistant Linux distant

```bash
python3 configure.py
```

Il demande les adresses sÃ©parÃ©es par des points-virgules, la collecte locale et le broker, puis crÃ©e config.generated.json sans Ã©craser de fichier. Sans interaction :

```bash
python3 configure.py --local --linux-hosts '192.0.2.31;192.0.2.32' \
  --mqtt-host mqtt.example.invalid --ssh-user monitor
```

Relire avant copie vers /etc/infra-agent/config.json. PrÃ©server les agent_id, identifiants de sources et sources IPMI existants.

### PrÃ©parer SSH

Chaque serveur distant doit avoir python3, un compte dÃ©diÃ© sans sudo autorisÃ© par clÃ© et accÃ¨s en lecture Ã  /proc, aux compteurs rÃ©seau et aux volumes choisis. lm-sensors est facultatif pour les tempÃ©ratures. Aucun service distant n'est installÃ© ; un programme de lecture est exÃ©cutÃ© en mÃ©moire.

Sur le collecteur :

```bash
sudo install -d -o infra-agent -g infra-agent -m 0700 /etc/infra-agent/ssh
sudo -u infra-agent ssh-keygen -t ed25519 -N '' -f /etc/infra-agent/ssh/id_ed25519
```

Installer la clÃ© .pub dans ~monitor/.ssh/authorized_keys du serveur distant ; prÃ©fÃ©rer les restrictions restrict et adresse source lorsque possible.

Obtenir et **vÃ©rifier l'empreinte de la clÃ© hÃ´te par un canal de confiance**, puis ajouter la clÃ© Ã  /etc/infra-agent/ssh/known_hosts. ssh-keyscan seul n'authentifie pas une clÃ©. Tester :

```bash
sudo -u infra-agent ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/etc/infra-agent/ssh/known_hosts \
  -i /etc/infra-agent/ssh/id_ed25519 monitor@192.0.2.31 'python3 --version'
```

Source distante :

```json
{"id":"linux-node1","type":"ssh_linux","host":"192.0.2.31","username":"monitor","private_key_file":"/etc/infra-agent/ssh/id_ed25519","known_hosts_file":"/etc/infra-agent/ssh/known_hosts","mounts":["/"]}
```

Le nom remonte du serveur sauf si name est renseignÃ©. Le temps de collecte s'ajoute Ã  l'intervalle ; adapter le nombre de sources et la frÃ©quence.

## iDRAC6 / IPMI

Activer IPMI sur le LAN, autoriser le compte IPMI au niveau USER et permettre UDP 623 depuis le collecteur. Les identifiants sont indÃ©pendants de VMware. Tester avec le vrai compte, sans mot de passe dans la commande :

```bash
read -rp 'Utilisateur IPMI : ' infra_bmc_user
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER mc info
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER sensor
ipmitool -I lanplus -C 3 -H 192.0.2.21 -U "$infra_bmc_user" -a -L USER dcmi power reading
```

cipher_suite: 3 vise iDRAC6 ; choisir le profil supportÃ© par votre matÃ©riel (17 possible sur BMC rÃ©cents). DCMI n'est pas universel : son absence laisse les autres sondes utilisables. Puissance = lecture instantanÃ©e DCMI ou sonde systÃ¨me reconnue, jamais addition des alimentations.

## VÃ©rifier et dÃ©marrer

```bash
sudo /usr/bin/python3 /opt/infra-agent/bridge.py /etc/infra-agent/config.json --check
sudo systemd-run --wait --pipe --collect \
  --property=User=infra-agent --property=Group=infra-agent \
  --property=EnvironmentFile=/etc/infra-agent/secrets.env \
  --working-directory=/opt/infra-agent \
  /usr/bin/python3 /opt/infra-agent/bridge.py /etc/infra-agent/config.json --once
```

--check valide sans connexion. --once lit sans publier sur MQTT ; le premier CPU/rÃ©seau local peut Ãªtre null car deux observations sont nÃ©cessaires. Retirer les informations privÃ©es avant de partager une sortie.

```bash
sudo systemctl enable --now infra-agent
systemctl is-enabled infra-agent
systemctl is-active infra-agent
sudo journalctl -u infra-agent -n 60 --no-pager
```

enable active le dÃ©marrage au reboot. MQTT Discovery doit Ãªtre activÃ© dans Home Assistant. Le broker doit autoriser les publications homeassistant/sensor/infra_* et infrastructure/<agent_id>/..., et l'abonnement au statut Home Assistant. Les topics des autres appareils ne sont pas modifiÃ©s.

AprÃ¨s modification : sudo systemctl restart infra-agent. Pour mettre Ã  jour, relancer l'installateur puis redÃ©marrer. Les configurations sont conservÃ©es.

Les sources en panne deviennent indisponibles. Les Ã©tats ne sont pas conservÃ©s comme mesures fraÃ®ches aprÃ¨s redÃ©marrage. mqtt.tls: true utilise la validation systÃ¨me du certificat ; adapter Ã©galement le port du broker (souvent 8883).
