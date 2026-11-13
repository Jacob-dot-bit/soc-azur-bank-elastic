#!/bin/bash
# Ajoute le pipeline sepa-transfer à Logstash sur siem-elk-01 (après install_logstash.sh). À lancer en root sur la VM :
#   bash install_sepa.sh [dossier contenant sepa-transfer.conf, sepa-beneficiaires.yml et pipelines.yml]
set -euo pipefail
SRC=${1:-/root/projet/infra/logstash}
cd /root/elastic
PW=$(sed -n 's/^elastic=//p' secrets.txt)
install -d -o root -g logstash -m 750 /etc/logstash/sepa
install -o root -g logstash -m 640 "$SRC/sepa-transfer.conf" /etc/logstash/conf.d/sepa-transfer.conf
install -o root -g logstash -m 640 "$SRC/sepa-beneficiaires.yml" /etc/logstash/sepa/beneficiaires.yml
[ -f /etc/logstash/pipelines.yml.orig ] || cp -p /etc/logstash/pipelines.yml /etc/logstash/pipelines.yml.orig
install -o root -g root -m 644 "$SRC/pipelines.yml" /etc/logstash/pipelines.yml

# Clé API limitée : écrire dans logs-sepa.transfer-* et rien d'autre (moindre privilège, comme pour SWIFT).
K=$(curl -s -f --cacert http_ca.crt -u "elastic:$PW" -X POST https://10.40.0.10:9200/_security/api_key \
  -H 'Content-Type: application/json' -d '{"name":"logstash-sepa","role_descriptors":{"logstash_sepa":{
    "cluster":["monitor"],"indices":[{"names":["logs-sepa.transfer-*"],"privileges":["auto_configure","create_doc"]}]}}}' \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["id"]+":"+d["api_key"])')
# Clé API et clé de hachage des IBAN dans /etc/default/logstash (root seul), jamais dans le pipeline ni dans git.
grep -v '^ES_LOGSTASH_SEPA_API_KEY=' /etc/default/logstash > /tmp/ls.env
echo "ES_LOGSTASH_SEPA_API_KEY=$K" >> /tmp/ls.env
grep -q '^SEPA_HASH_KEY=' /tmp/ls.env || echo "SEPA_HASH_KEY=$(openssl rand -hex 32)" >> /tmp/ls.env
install -o root -g root -m 600 /tmp/ls.env /etc/default/logstash; rm -f /tmp/ls.env
systemctl restart logstash
echo "Attente des ports 5514 et 5515..."
until ss -ltn | grep -q ':5515 ' && ss -ltn | grep -q ':5514 '; do sleep 5; done
echo "Logstash prêt : swift-gateway (TCP 5514) et sepa-transfer (TCP 5515)"
