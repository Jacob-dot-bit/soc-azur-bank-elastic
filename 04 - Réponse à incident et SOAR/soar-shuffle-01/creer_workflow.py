#!/usr/bin/env python3
"""Crée (ou recrée) le workflow Shuffle « Azur Bank - Réponse exfiltration et fraude SWIFT ».

À lancer en root sur soar-shuffle-01 : python3 creer_workflow.py <dossier playbook> <fichier variables>
Le fichier de variables contient des lignes nom=valeur (les valeurs multilignes sont lues dans
des fichiers : ca_soc=@/chemin/ca.pem). Les secrets ne sont donc pas dans ce script.
"""
import json, ssl, sys, uuid, urllib.request
from pathlib import Path

PLAY, VARS = Path(sys.argv[1]), Path(sys.argv[2])
API = "https://127.0.0.1:3443/api/v1"
KEY = [l.split("=", 1)[1] for l in open("/root/shuffle-secrets.txt").read().splitlines() if l.startswith("api_key=")][0]
CTX = ssl._create_unverified_context()  # Shuffle sur la même machine, certificat auto-signé

def api(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        t = r.read().decode(); return json.loads(t) if t.strip().startswith(("{", "[")) else t

NOM = "Azur Bank - Réponse exfiltration et fraude SWIFT"
tools = [a for a in api("GET", "/apps") if a["name"] == "Shuffle Tools"][0]

variables = []
for l in VARS.read_text().splitlines():
    if not l.strip() or l.startswith("#"): continue
    n, v = l.split("=", 1)
    if v.startswith("@"): v = Path(v[1:]).read_text()
    variables.append({"id": str(uuid.uuid4()), "name": n, "value": v, "description": ""})

noeuds = [("lire_alertes", "1_lire_alertes.py"), ("ouvrir_case", "2_ouvrir_case.py"),
          ("reponse", "3_reponse.py"), ("cloturer", "4_cloturer.py")]
actions = []
for k, (label, fichier) in enumerate(noeuds):
    actions.append({"id": str(uuid.uuid4()), "app_name": "Shuffle Tools", "app_version": tools["app_version"],
                    "app_id": tools["id"], "name": "execute_python", "label": label, "environment": "Shuffle",
                    "is_valid": True, "isStartNode": k == 0, "position": {"x": 250 + 280 * k, "y": 300},
                    "parameters": [{"name": "code", "value": (PLAY / fichier).read_text(), "required": True,
                                    "multiline": True, "schema": {"type": "string"}}]})
branches = [{"id": str(uuid.uuid4()), "source_id": a["id"], "destination_id": b["id"], "conditions": []}
            for a, b in zip(actions, actions[1:])]
# Arrêt propre quand il n'y a rien à traiter : condition sur la sortie du premier noeud
branches[0]["conditions"] = [{
    "source": {"name": "source", "value": "$lire_alertes.message.nb", "variant": "STATIC_VALUE", "action_field": "", "id": str(uuid.uuid4())},
    "condition": {"name": "condition", "value": "larger than", "id": str(uuid.uuid4())},
    "destination": {"name": "destination", "value": "0", "variant": "STATIC_VALUE", "action_field": "", "id": str(uuid.uuid4())}}]
trig_id = str(uuid.uuid4())
trigger = {"id": trig_id, "name": "Toutes les minutes", "label": "toutes_les_minutes", "app_name": "Schedule",
           "trigger_type": "SCHEDULE", "status": "uninitialized", "environment": "Shuffle", "is_valid": True,
           "position": {"x": 50, "y": 300}, "large_image": "",
           "parameters": [{"name": "cron", "value": "60"}, {"name": "execution_argument", "value": ""}]}
branches.insert(0, {"id": str(uuid.uuid4()), "source_id": trig_id, "destination_id": actions[0]["id"], "conditions": []})

for w in api("GET", "/workflows"):
    if w.get("name") == NOM:
        api("DELETE", f"/workflows/{w['id']}")
wf = api("POST", "/workflows", {"name": NOM, "description": "Lit les alertes Elastic (exfiltration base clients, "
         "virement SWIFT anormal), ouvre un case Kibana, confine le compte (base, AD) et bloque l'IP externe."})
wf.update({"actions": actions, "branches": branches, "triggers": [trigger], "start": actions[0]["id"],
           "workflow_variables": variables, "tags": ["azur-bank", "soc-run"]})
api("PUT", f"/workflows/{wf['id']}", wf)
r = api("POST", f"/workflows/{wf['id']}/schedule", {"name": trigger["name"], "frequency": "60",
        "execution_argument": "", "environment": "Shuffle", "id": trig_id, "start": actions[0]["id"]})
print("workflow", wf["id"], "planification :", str(r)[:200])
