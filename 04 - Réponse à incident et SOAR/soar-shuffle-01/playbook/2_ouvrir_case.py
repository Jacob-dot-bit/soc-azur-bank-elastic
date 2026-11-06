# Noeud 2 : un case Kibana par incident (compte + type), avec ses alertes attachées.
import json, requests, tempfile
ca = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False); ca.write("""$ca_soc"""); ca.close()
data = json.loads(r'''$lire_alertes.message''')
H = {"Authorization": "ApiKey $es_api_key", "kbn-xsrf": "true", "Content-Type": "application/json"}
KB = "$kb_url"
for i in data["incidents"]:
    if i["type"] == "swift":
        titre = f"[SOAR] Virement SWIFT anormal - opérateur {i['user']}"
        desc = "Virement(s) hors norme détecté(s) sur la passerelle SWIFT : " + ", ".join(
            f"{s.get('ref')} {s.get('amount')} EUR vers {s.get('receiver')}" for s in i["swift"])
    else:
        titre = f"[SOAR] Exfiltration base clients - compte {i['user']}"
        desc = (f"Lecture massive de la table clients puis export par {i['user']} depuis "
                f"{', '.join(i['source_ip']) or 'IP inconnue'}. Règles : "
                + ", ".join(sorted({r['name'] for r in i['regles']})))
    # Un case déjà ouvert pour ce compte et ce type ? On y rattache les nouvelles alertes (pas de doublon).
    ouverts = requests.get(f"{KB}/api/cases/_find", headers=H, verify=ca.name, timeout=30,
                           params={"tags": "soar", "status": "open", "perPage": 100}).json().get("cases", [])
    existant = [k for k in ouverts if k["title"] == titre]
    if existant:
        case = existant[0]; i["case_reutilise"] = True
    else:
      c = requests.post(f"{KB}/api/cases", headers=H, verify=ca.name, timeout=30, json={
        "title": titre, "description": desc + "\n\nCase ouvert automatiquement par Shuffle (playbook Azur Bank).",
        "tags": ["soar", "azur-bank", i["type"]], "severity": i["severite"], "owner": "securitySolution",
        "connector": {"id": "none", "name": "none", "type": ".none", "fields": None},
        "settings": {"syncAlerts": True}})
      c.raise_for_status(); case = c.json()
    regle = i["regles"][0]
    a = requests.post(f"{KB}/api/cases/{case['id']}/comments", headers=H, verify=ca.name, timeout=30, json={
        "type": "alert", "owner": "securitySolution", "alertId": i["alertes"], "index": i["index"],
        "rule": {"id": regle["id"], "name": regle["name"]}})
    a.raise_for_status()
    i["case_id"] = case["id"]; i["case_url"] = f"{KB}/app/security/cases/{case['id']}"
print(json.dumps(data))
