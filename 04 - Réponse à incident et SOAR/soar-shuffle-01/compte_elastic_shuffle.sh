# Role et cle API de Shuffle sur le SIEM : lire/annoter les alertes, gerer les cases. Rien d'autre.
set -e
cd /root/elastic
K=$(sed -n 's/^api_key=//p' secrets.txt)
H=(-s -f --cacert pki/ca/ca.crt -H "Authorization: ApiKey $K" -H kbn-xsrf:true -H Content-Type:application/json)
curl "${H[@]}" -X PUT https://10.40.0.10:5601/api/security/role/soar_shuffle -d '{
 "elasticsearch":{"cluster":["manage_own_api_key"],"indices":[{"names":[".alerts-security.alerts-*",".internal.alerts-security.alerts-*"],"privileges":["read","write","view_index_metadata","maintenance"]},
                             {"names":["logs-*"],"privileges":["read"]}]},
 "kibana":[{"base":[],"spaces":["default"],"feature":{"siemV5":["read"],"securitySolutionAlertsV1":["all"],"securitySolutionCasesV3":["all"]}}]}' -o /dev/null -w "role %{http_code}\n"
PW=$(openssl rand -base64 24 | tr -d '/+=')
curl -s --cacert http_ca.crt -H "Authorization: ApiKey $K" -H Content-Type:application/json -X POST https://10.40.0.10:9200/_security/user/svc-shuffle \
  -d "{\"password\":\"$PW\",\"roles\":[\"soar_shuffle\"],\"full_name\":\"Compte SOAR Shuffle\"}" -o /dev/null -w "user %{http_code}\n"
AK=$(curl -s -f --cacert http_ca.crt -u "svc-shuffle:$PW" -H Content-Type:application/json -X POST https://10.40.0.10:9200/_security/api_key -d '{"name":"shuffle-soar"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["encoded"])')
umask 077
grep -v '^shuffle_' secrets.txt > s.tmp || true; mv s.tmp secrets.txt
echo "shuffle_user_password=$PW" >> secrets.txt
echo "shuffle_api_key=$AK" >> secrets.txt
echo ok
