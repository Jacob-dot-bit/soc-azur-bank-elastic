# Noeud 1 du playbook « Réponse exfiltration / fraude » : lit les alertes ouvertes, pas encore traitées.
# Variables Shuffle : es_url, es_api_key, ca_soc (certificats des CA du SOC, PEM)
import json, requests, tempfile
ca = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False); ca.write("""$ca_soc"""); ca.close()
REGLES = ["azur-bank-client-data-exfil", "azur-bank-client-data-exfil-sequence",
          "azur-bank-client-data-exfil-esql", "azur-bank-swift-virement-anormal"]
q = {"size": 100, "sort": [{"@timestamp": "asc"}],
     "_source": ["@timestamp", "user.name", "source.ip", "kibana.alert.rule.name", "kibana.alert.rule.uuid",
                 "kibana.alert.rule.rule_id", "kibana.alert.severity", "swift.ref", "swift.amount", "swift.receiver"],
     "query": {"bool": {
         "filter": [{"term": {"kibana.alert.workflow_status": "open"}},
                    {"terms": {"kibana.alert.rule.rule_id": REGLES}}],
         "must_not": [{"term": {"kibana.alert.workflow_tags": "soar-traite"}},
                      {"exists": {"field": "kibana.alert.building_block_type"}}]}}}
r = requests.post("$es_url/.alerts-security.alerts-default/_search", json=q, verify=ca.name, timeout=30,
                  headers={"Authorization": "ApiKey $es_api_key"})
r.raise_for_status()
incidents = {}
def champ(s, nom):
    # les alertes stockent les champs soit à plat ("user.name"), soit imbriqués ({"user": {"name"}})
    if nom in s: return s[nom]
    v = s
    for k in nom.split("."):
        if not isinstance(v, dict) or k not in v: return None
        v = v[k]
    return v
for h in r.json()["hits"]["hits"]:
    s = h["_source"]
    user = champ(s, "user.name") or "inconnu"
    if isinstance(user, list): user = user[0]
    regle = s["kibana.alert.rule.rule_id"]
    type_ = "swift" if "swift" in regle else "exfiltration"
    i = incidents.setdefault(type_ + ":" + user, {"type": type_, "user": user, "alertes": [], "index": [],
                                                  "regles": [], "source_ip": [], "severite": "high", "swift": []})
    i["alertes"].append(h["_id"]); i["index"].append(h["_index"])
    i["regles"].append({"id": s["kibana.alert.rule.uuid"], "name": s["kibana.alert.rule.name"]})
    ip = champ(s, "source.ip")
    if isinstance(ip, list): ip = ip[0] if ip else None
    if ip and ip not in i["source_ip"]: i["source_ip"].append(ip)
    if s.get("kibana.alert.severity") == "critical": i["severite"] = "critical"
    sw = {k: champ(s, "swift." + k) for k in ("ref", "amount", "receiver")}
    if sw["ref"]: i["swift"].append(sw)
print(json.dumps({"nb": len(incidents), "incidents": list(incidents.values())}))
