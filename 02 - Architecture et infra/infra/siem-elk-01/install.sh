#!/bin/bash
# Installation de siem-elk-01 : Elasticsearch + Kibana (licence Basic, gratuite, sans date de fin).
# À lancer en root sur la VM (Debian 13), avec les paquets dans /root/elastic :
#   elasticsearch-<V>-amd64.deb, kibana-<V>-amd64.deb, elastic-agent-<V>-linux-x86_64.tar.gz
# Le mot de passe du compte elastic est écrit dans /root/elastic/secrets.txt (lisible par root seul).
# Fleet Server est installé ensuite par fleet-server.sh (il a besoin de Kibana).
set -euo pipefail
IP=10.40.0.10
NOM=siem-elk-01
cd /root/elastic

# 1. Système : Elasticsearch veut beaucoup de « memory maps » et pas de swap.
echo "vm.max_map_count=262144" > /etc/sysctl.d/90-elasticsearch.conf
sysctl -q --system
swapoff -a

# 2. Elasticsearch. Le paquet active la sécurité tout seul (TLS sur 9200, compte elastic).
dpkg -i elasticsearch-*-amd64.deb | tee /root/elastic/install-es.log
python3 - <<EOF
import re
p = "/etc/elasticsearch/elasticsearch.yml"
s = open(p).read()
s = re.sub(r"^#?cluster\.name:.*$", "cluster.name: azurbank-soc", s, flags=re.M)
s = re.sub(r"^#?node\.name:.*$", "node.name: $NOM", s, flags=re.M)
s = re.sub(r"^#?network\.host:.*$", "network.host: $IP", s, flags=re.M)
open(p, "w").write(s)
EOF
# Tas Java : 4 Go sur 10 Go de RAM (la moitié au plus, le reste sert au cache disque et à Kibana).
printf -- "-Xms4g\n-Xmx4g\n" > /etc/elasticsearch/jvm.options.d/heap.options
chown root:elasticsearch /etc/elasticsearch/jvm.options.d/heap.options; chmod 640 /etc/elasticsearch/jvm.options.d/heap.options
systemctl daemon-reload
systemctl enable --now elasticsearch

# Nouveau mot de passe elastic, gardé dans secrets.txt.
PW=$(/usr/share/elasticsearch/bin/elasticsearch-reset-password -u elastic -a -b -s)
(umask 077; echo "elastic=$PW" > /root/elastic/secrets.txt)
cp /etc/elasticsearch/certs/http_ca.crt /root/elastic/http_ca.crt
curl -s --cacert /root/elastic/http_ca.crt -u "elastic:$PW" "https://$IP:9200/_license" | grep -E '"type"|"status"'

# 3. Autorité de certification du SOC, pour Kibana et Fleet Server (les agents lui feront confiance).
CU=/usr/share/elasticsearch/bin/elasticsearch-certutil
mkdir -p /root/elastic/pki && cd /root/elastic/pki
[ -f ca.zip ] || $CU ca --pem --out /root/elastic/pki/ca.zip --days 3650 --ca-dn "CN=Azur Bank SOC CA"
python3 -m zipfile -e ca.zip .
[ -f certs.zip ] || { cat > instances.yml <<EOF
instances:
  - name: $NOM
    dns: [$NOM, $NOM.azurbank.local, localhost]
    ip: [$IP, 127.0.0.1]
EOF
$CU cert --pem --in /root/elastic/pki/instances.yml --ca-cert /root/elastic/pki/ca/ca.crt --ca-key /root/elastic/pki/ca/ca.key --out /root/elastic/pki/certs.zip --days 1095; }
python3 -m zipfile -e certs.zip .
cd /root/elastic

# 4. Kibana, en HTTPS, enrôlé auprès d'Elasticsearch avec un jeton à usage unique.
dpkg -i kibana-*-amd64.deb | tee /root/elastic/install-kibana.log
install -d -o root -g kibana -m 750 /etc/kibana/certs
install -o root -g kibana -m 640 pki/ca/ca.crt pki/$NOM/$NOM.crt pki/$NOM/$NOM.key /etc/kibana/certs/
TOKEN=$(/usr/share/elasticsearch/bin/elasticsearch-create-enrollment-token -s kibana --url "https://$IP:9200")
/usr/share/kibana/bin/kibana-setup --enrollment-token "$TOKEN"
# Clés de chiffrement des objets enregistrés : obligatoires pour les règles de détection et les alertes.
KEYS=$(/usr/share/kibana/bin/kibana-encryption-keys generate -q | grep '^xpack')
cat >> /etc/kibana/kibana.yml <<EOF

# --- Azur Bank SOC ---
server.host: "$IP"
server.name: "$NOM"
server.publicBaseUrl: "https://$IP:5601"
server.ssl.enabled: true
server.ssl.certificate: /etc/kibana/certs/$NOM.crt
server.ssl.key: /etc/kibana/certs/$NOM.key
i18n.locale: "fr-FR"
$KEYS
EOF
systemctl enable --now kibana
echo "Attente de Kibana..."
until curl -s --cacert pki/ca/ca.crt "https://$IP:5601/api/status" | grep -q '"level":"available"'; do sleep 5; done
echo "Kibana prêt : https://$IP:5601 (compte elastic, mot de passe dans /root/elastic/secrets.txt)"
