#!/bin/bash
# Installe Logstash sur siem-elk-01 avec le pipeline swift-gateway. À lancer en root sur la VM,
# après install.sh (il faut /root/elastic/http_ca.crt et le compte elastic dans secrets.txt).
set -euo pipefail
cd /root/elastic
PW=$(sed -n 's/^elastic=//p' secrets.txt)
dpkg -i logstash-*-amd64.deb >/dev/null
# Tas Java réduit : la VM partage ses 10 Go avec Elasticsearch (4 Go) et Kibana.
sed -i 's/^-Xms.*/-Xms768m/; s/^-Xmx.*/-Xmx768m/' /etc/logstash/jvm.options
install -d -o root -g logstash -m 750 /etc/logstash/certs
install -o root -g logstash -m 640 http_ca.crt /etc/logstash/certs/
install -o root -g logstash -m 640 /root/projet/infra/logstash/swift-gateway.conf /etc/logstash/conf.d/swift-gateway.conf

# Clé API limitée : écrire dans logs-swift.gateway-* et rien d'autre (principe du moindre privilège).
K=$(curl -s -f --cacert http_ca.crt -u "elastic:$PW" -X POST https://10.40.0.10:9200/_security/api_key \
  -H 'Content-Type: application/json' -d '{"name":"logstash-swift","role_descriptors":{"logstash_swift":{
    "cluster":["monitor"],"indices":[{"names":["logs-swift.gateway-*"],"privileges":["auto_configure","create_doc"]}]}}}' \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["id"]+":"+d["api_key"])')
# Rangée dans /etc/default/logstash (lu par systemd, root seul), pas dans le fichier de pipeline.
grep -v '^ES_LOGSTASH_API_KEY=' /etc/default/logstash 2>/dev/null > /tmp/ls.env || true
echo "ES_LOGSTASH_API_KEY=$K" >> /tmp/ls.env
install -o root -g root -m 600 /tmp/ls.env /etc/default/logstash; rm -f /tmp/ls.env
rm -f /etc/logstash/logstash.keystore
systemctl enable logstash; systemctl restart logstash
echo "Attente du port 5514..."
until ss -ltn | grep -q ':5514 '; do sleep 5; done
echo "Logstash prêt (TCP 10.40.0.10:5514)"
