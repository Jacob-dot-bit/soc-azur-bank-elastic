#!/bin/bash
# Fleet Server sur siem-elk-01 (après install.sh). À lancer en root sur la VM.
# 1) configure Fleet dans Kibana (hôte Fleet Server, sortie Elasticsearch, politique fleet-server)
# 2) installe l'Elastic Agent en mode Fleet Server, en HTTPS 8220 avec le certificat de la CA du SOC.
set -euo pipefail
IP=10.40.0.10
NOM=siem-elk-01
cd /root/elastic
PW=$(sed -n 's/^elastic=//p' secrets.txt)
KB="https://$IP:5601"
kb() { curl -s -f --cacert pki/ca/ca.crt -u "elastic:$PW" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' "$@"; }

# Empreinte SHA-256 de la CA HTTP d'Elasticsearch : les agents l'utilisent pour faire confiance à la sortie 9200.
FP=$(openssl x509 -in http_ca.crt -noout -fingerprint -sha256 | cut -d= -f2 | tr -d :)

kb -X POST "$KB/api/fleet/setup" >/dev/null
kb -X PUT "$KB/api/fleet/outputs/fleet-default-output" -d "{\"name\":\"default\",\"type\":\"elasticsearch\",
  \"hosts\":[\"https://$IP:9200\"],\"ca_trusted_fingerprint\":\"$FP\",\"is_default\":true,\"is_default_monitoring\":true}" >/dev/null \
  || echo "(sortie préconfigurée par kibana-setup dans kibana.yml : déjà correcte)"
kb -X POST "$KB/api/fleet/fleet_server_hosts" -d "{\"id\":\"siem-elk-01\",\"name\":\"siem-elk-01\",
  \"host_urls\":[\"https://$IP:8220\"],\"is_default\":true}" >/dev/null || echo "(hôte Fleet Server déjà déclaré)"
kb -X POST "$KB/api/fleet/agent_policies?sys_monitoring=true" -d '{"id":"fleet-server-policy","name":"fleet-server-policy",
  "namespace":"default","description":"Fleet Server on-prem (siem-elk-01)","has_fleet_server":true,
  "monitoring_enabled":["logs","metrics"]}' >/dev/null || echo "(politique fleet-server-policy déjà créée)"

# Jeton de service pour Fleet Server (droits limités à Fleet, pas le compte elastic).
TOKEN=$(curl -s -f --cacert http_ca.crt -u "elastic:$PW" -X POST \
  "https://$IP:9200/_security/service/elastic/fleet-server/credential/token/fs-$(date +%s)" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"]["value"])')

install -d -m 755 /etc/azurbank-ca
install -m 644 pki/ca/ca.crt /etc/azurbank-ca/soc-ca.crt
install -m 644 http_ca.crt /etc/azurbank-ca/es-http-ca.crt
install -d -m 700 /etc/azurbank-ca/fleet
install -m 600 pki/$NOM/$NOM.crt pki/$NOM/$NOM.key /etc/azurbank-ca/fleet/

tar xzf elastic-agent-*-linux-x86_64.tar.gz
cd elastic-agent-*-linux-x86_64
./elastic-agent install -n \
  --url="https://$IP:8220" \
  --fleet-server-es="https://$IP:9200" \
  --fleet-server-es-ca=/etc/azurbank-ca/es-http-ca.crt \
  --fleet-server-service-token="$TOKEN" \
  --fleet-server-policy=fleet-server-policy \
  --fleet-server-port=8220 \
  --fleet-server-cert=/etc/azurbank-ca/fleet/$NOM.crt \
  --fleet-server-cert-key=/etc/azurbank-ca/fleet/$NOM.key \
  --certificate-authorities=/etc/azurbank-ca/soc-ca.crt
sleep 10
curl -s --cacert /etc/azurbank-ca/soc-ca.crt "https://$IP:8220/api/status"; echo
