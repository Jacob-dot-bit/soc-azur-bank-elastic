# Noeud 4 : trace dans le case, alertes passées en « acknowledged » et étiquetées soar-traite.
import json, requests, tempfile
ca = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False); ca.write("""$ca_soc"""); ca.close()
data = json.loads(r'''$reponse.message''')
H = {"Authorization": "ApiKey $es_api_key", "kbn-xsrf": "true", "Content-Type": "application/json"}
KB = "$kb_url"
bilan = []
for i in data["incidents"]:
    texte = "Actions du playbook Shuffle :\n" + "\n".join(f"- {a}" for a in i.get("actions", []))
    requests.post(f"{KB}/api/cases/{i['case_id']}/comments", headers=H, verify=ca.name, timeout=30,
                  json={"type": "user", "owner": "securitySolution", "comment": texte}).raise_for_status()
    requests.post(f"{KB}/api/detection_engine/signals/tags", headers=H, verify=ca.name, timeout=30,
                  json={"ids": i["alertes"], "tags": {"tags_to_add": ["soar-traite"], "tags_to_remove": []}}).raise_for_status()
    requests.post(f"{KB}/api/detection_engine/signals/status", headers=H, verify=ca.name, timeout=30,
                  json={"signal_ids": i["alertes"], "status": "acknowledged"}).raise_for_status()
    bilan.append({"user": i["user"], "type": i["type"], "case": i["case_url"], "alertes": len(i["alertes"]),
                  "actions": i.get("actions", [])})
print(json.dumps({"incidents_traites": len(bilan), "bilan": bilan}, ensure_ascii=False))
