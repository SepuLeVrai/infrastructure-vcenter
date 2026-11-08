#!/usr/bin/env bash
# Installs collector files/packages. Start the service after configuring it.
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo 'Lancer avec sudo bash install-debian.sh' >&2
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
apt-get update
apt-get install -y --no-install-recommends python3 python3-paho-mqtt ipmitool lm-sensors openssh-client
if ! id infra-agent >/dev/null 2>&1; then
  useradd --system --user-group --no-create-home --shell /usr/sbin/nologin infra-agent
fi
install -d -o root -g root -m 0755 /opt/infra-agent
install -d -o root -g infra-agent -m 0750 /etc/infra-agent
for name in bridge.py providers.py configure.py; do
  if ! test "$script_dir/$name" -ef "/opt/infra-agent/$name"; then
    install -o root -g root -m 0644 "$script_dir/$name" "/opt/infra-agent/$name"
  fi
done
if [[ ! -e /etc/infra-agent/config.json ]]; then
  install -o root -g infra-agent -m 0640 "$script_dir/config.example.json" /etc/infra-agent/config.json
fi
if [[ ! -e /etc/infra-agent/secrets.env ]]; then
  install -o root -g root -m 0600 "$script_dir/secrets.env.example" /etc/infra-agent/secrets.env
fi
install -o root -g root -m 0644 "$script_dir/infra-agent.service" /etc/systemd/system/infra-agent.service
systemctl daemon-reload
echo 'Installation préparée. Configuration et secrets existants conservés.'
echo 'Renseigner /etc/infra-agent/config.json et /etc/infra-agent/secrets.env avant de démarrer le service.'
