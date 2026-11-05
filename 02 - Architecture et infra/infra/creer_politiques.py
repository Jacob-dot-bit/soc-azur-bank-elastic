#!/usr/bin/env python3
"""Crée les politiques Fleet d'Azur Bank (Kibana Fleet API). Clé lue dans ES_API_KEY, jamais écrite.

On-prem : KB_URL=https://10.40.0.10:5601 et ES_CA=chemin du certificat de la CA du SOC (soc-ca.crt).
"""
import json, os, ssl, sys, urllib.request, urllib.error

KB = os.environ["KB_URL"]  # ex. https://10.40.0.10:5601 (on-prem) ou https://<projet>.kb.<region>.gcp.elastic.cloud
H = {"Authorization": "ApiKey " + os.environ["ES_API_KEY"], "kbn-xsrf": "true", "Content-Type": "application/json",
     "Elastic-Api-Version": "2023-10-31"}

CTX = ssl.create_default_context(cafile=os.environ.get("ES_CA") or None)

def api(method, path, body=None):
    req = urllib.request.Request(KB + path, method=method, headers=H, data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, context=CTX) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        print("ERREUR", method, path, e.code, e.read().decode()[:800]); sys.exit(1)

def version(pkg): return api("GET", f"/api/fleet/epm/packages/{pkg}")["item"]["version"]

existing = {p["name"]: p["id"] for p in api("GET", "/api/fleet/agent_policies?perPage=100")["items"]}
def policy(name, desc):
    if name in existing: return existing[name]
    p = api("POST", "/api/fleet/agent_policies", {"name": name, "namespace": "default", "description": desc,
                                                  "monitoring_enabled": ["logs", "metrics"]})["item"]
    print("politique", name, p["id"]); return p["id"]

def pkgpol(pid, name, pkg, inputs=None, vars=None):
    body = {"policy_id": pid, "name": name, "namespace": "default", "package": {"name": pkg, "version": version(pkg)}}
    if inputs: body["inputs"] = inputs
    if vars: body["vars"] = vars
    r = api("POST", "/api/fleet/package_policies", body)["item"]; print("  integration", name, r["id"])

db = policy("pol-linux-db", "db-clients-01 : System + audit PostgreSQL (pgaudit) vers logs-db.audit-*")
pkgpol(db, "system-db", "system")
pkgpol(db, "pgaudit-db-audit", "filestream", inputs={"filestream-filestream": {"enabled": True, "streams": {
    "filestream.filestream": {"enabled": True, "vars": {
        "paths": ["/var/log/postgresql/postgresql-*-main.log"], "data_stream.dataset": "db.audit",
        "pipeline": "db-audit-pgaudit", "tags": ["pgaudit", "azurbank"],
        "processors": "- add_fields:\n    target: ''\n    fields:\n      organization.name: Azur Bank\n"}}}}})

web = policy("pol-linux-web", "web-portail-01 : System + Nginx (logs-nginx.access-*)")
pkgpol(web, "system-web", "system")
pkgpol(web, "nginx-portail", "nginx", inputs={"nginx-nginx/metrics": {"enabled": False}})

bas = policy("pol-linux-bastion", "bastion-01 : System (auth) + syslog fw-01 OPNsense (UDP 514)")
pkgpol(bas, "system-bastion", "system")
pkgpol(bas, "opnsense-fw01", "pfsense", inputs={
    "pfsense-udp": {"enabled": True, "streams": {"pfsense.log": {"enabled": True, "vars": {
        "syslog_host": "0.0.0.0", "syslog_port": 514, "internal_networks": ["private"], "tz_offset": "UTC"}}}},
    "pfsense-tcp": {"enabled": False}})

win = policy("pol-windows", "Postes et serveurs Windows : System, Windows (Sysmon, PowerShell), Elastic Defend")
pkgpol(win, "system-windows", "system")
pkgpol(win, "windows-sysmon", "windows")
if "pol-windows" not in existing:
    # Elastic Defend (EDR) : en licence Basic, prévention malware et événements endpoint.
    pkgpol(win, "elastic-defend-windows", "endpoint", inputs=[{"type": "endpoint", "enabled": True, "streams": [],
           "config": {"_config": {"value": {"type": "endpoint", "endpointConfig": {"preset": "EDRComplete"}}}}}])
