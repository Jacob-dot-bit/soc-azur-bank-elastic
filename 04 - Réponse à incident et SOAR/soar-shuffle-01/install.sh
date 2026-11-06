#!/bin/bash
# Installation de Shuffle (SOAR open source) sur soar-shuffle-01 (Debian 13, zone SOC, 10.40.0.20).
# À lancer en root. Secrets générés dans /root/shuffle-secrets.txt (root seul).
set -euo pipefail
VERSION=v2.3.0
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io docker-compose git qemu-guest-agent openssl
echo "vm.max_map_count=262144" > /etc/sysctl.d/90-opensearch.conf; sysctl -q --system

[ -d /opt/shuffle ] || git clone -q --depth 1 --branch $VERSION https://github.com/Shuffle/Shuffle /opt/shuffle
cd /opt/shuffle
if [ ! -f /root/shuffle-secrets.txt ]; then
  umask 077
  { echo "admin_user=admin.soc"
    echo "admin_password=$(openssl rand -base64 18 | tr -d '/+=')Aa1!"
    echo "api_key=$(cat /proc/sys/kernel/random/uuid)"
    echo "opensearch_password=$(openssl rand -base64 18 | tr -d '/+=')Aa1!"
    echo "encryption=$(openssl rand -hex 16)"; } > /root/shuffle-secrets.txt
  umask 022
fi
get() { sed -n "s/^$1=//p" /root/shuffle-secrets.txt; }
OSP=$(get opensearch_password)
sed -i \
  -e "s|^SHUFFLE_DEFAULT_USERNAME=.*|SHUFFLE_DEFAULT_USERNAME=$(get admin_user)|" \
  -e "s|^SHUFFLE_DEFAULT_PASSWORD=.*|SHUFFLE_DEFAULT_PASSWORD=$(get admin_password)|" \
  -e "s|^SHUFFLE_DEFAULT_APIKEY=.*|SHUFFLE_DEFAULT_APIKEY=$(get api_key)|" \
  -e "s|^SHUFFLE_ENCRYPTION_MODIFIER=.*|SHUFFLE_ENCRYPTION_MODIFIER=$(get encryption)|" \
  -e "s|^SHUFFLE_OPENSEARCH_PASSWORD=.*|SHUFFLE_OPENSEARCH_PASSWORD=\"$OSP\"|" \
  -e "s|^OPENSEARCH_INITIAL_ADMIN_PASSWORD=.*|OPENSEARCH_INITIAL_ADMIN_PASSWORD=\"$OSP\"|" \
  -e "s|^TZ=.*|TZ=Europe/Paris|" \
  -e "s|^SHUFFLE_APP_REPLICAS=.*|SHUFFLE_APP_REPLICAS=1|" .env
chmod 600 .env
# OpenSearch interne de Shuffle : 1,5 Go de tas (VM de 6 Go) et pas de port publié hors de Docker.
sed -i -e 's/-Xms3072m -Xmx3072m/-Xms1536m -Xmx1536m/' docker-compose.yml
python3 - <<'PY'
p = "docker-compose.yml"; s = open(p).read()
s = s.replace("    ports:\n      - 9200:9200\n", "")
open(p, "w").write(s)
PY
mkdir -p shuffle-apps shuffle-files shuffle-database
chown -R 1000:1000 shuffle-database
docker-compose up -d
echo "Attente de Shuffle (https://10.40.0.20:3443)..."
until curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1:3443/ | grep -q 200; do sleep 10; done
until curl -sk -H "Authorization: Bearer $(get api_key)" https://127.0.0.1:3443/api/v1/users/getinfo | grep -q '"success": *true\|"username"'; do sleep 10; done
echo "Shuffle prêt"
