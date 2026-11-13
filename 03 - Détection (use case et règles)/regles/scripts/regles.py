#!/usr/bin/env python3
"""Déploie et vérifie les règles du use case « exfiltration de données clients ».

Variables d'environnement :
    ES_URL      https://<projet>.es.<region>.elastic.cloud:443
    ES_API_KEY  clé API encodée (base64 id:key)
    KB_URL      URL de Kibana ; optionnelle sur Elastic Cloud (déduite de ES_URL, .es. -> .kb.),
                obligatoire on-prem (ex. https://10.40.0.10:5601)
    ES_CA       optionnel : certificat de l'autorité du cluster on-prem (http_ca.crt)
    REGLES      optionnel : dossier de règles, « elastic » (défaut, Elastic Cloud)
                ou « elastic-basic » (instance on-prem en licence Basic)

Sous-commandes :
    check            vérifie les données, l'exfiltration injectée, EQL (runs) et ES|QL
    deploy           crée ou met à jour les règles du dossier choisi par REGLES
    run DEBUT FIN    lance une exécution manuelle des règles sur une période passée (ISO 8601)
    alerts           liste les alertes produites par ces règles
"""
import glob
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "..", os.environ.get("REGLES", "elastic"))
RULE_IDS = ["azur-bank-client-data-exfil", "azur-bank-client-data-exfil-sequence", "azur-bank-client-data-exfil-esql",
            "azur-bank-swift-virement-anormal",
            "azur-bank-portail-sqli", "azur-bank-bastion-brute-force",
            "azur-bank-ad-groupe-privilegie", "azur-bank-effacement-journal", "azur-bank-admin-hors-horaires"]

ES_URL = os.environ.get("ES_URL", "").rstrip("/")
KEY = os.environ.get("ES_API_KEY")
if not ES_URL or not KEY:
    sys.exit("Définir ES_URL et ES_API_KEY")
if not ES_URL.startswith("http"):
    ES_URL = "https://" + ES_URL
KB_URL = os.environ.get("KB_URL", ES_URL.replace(".es.", ".kb.")).rstrip("/")
CTX = ssl.create_default_context(cafile=os.environ.get("ES_CA") or None)


def call(base, method, path, body=None, kibana=False):
    headers = {"Authorization": f"ApiKey {KEY}", "Content-Type": "application/json"}
    if kibana:
        headers.update({"kbn-xsrf": "true", "elastic-api-version": "2023-10-31"})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(txt)
        except ValueError:
            return e.code, txt


def es(method, path, body=None):
    return call(ES_URL, method, path, body)


def kb(method, path, body=None):
    return call(KB_URL, method, path, body, kibana=True)


def show(title, res):
    print(f"\n### {title} -> HTTP {res[0]}")
    print(json.dumps(res[1], ensure_ascii=False, indent=2)[:3000])


def check():
    show("Cluster", es("GET", "/"))
    show("Docs par dataset", es("POST", "/logs-*-banque/_search", {
        "size": 0, "aggs": {"ds": {"terms": {"field": "event.dataset"}}}}))
    show("Mapping object / user.name", es("GET", "/logs-db.audit-banque/_mapping/field/object,user.name,event.action"))
    show("Fenêtre de l'exfiltration (selects clients par compte, top 3)", es("POST", "/logs-db.audit-*/_search", {
        "size": 0, "query": {"bool": {"filter": [{"term": {"event.action": "select"}}, {"term": {"object": "clients"}}]}},
        "aggs": {"u": {"terms": {"field": "user.name", "size": 3},
                       "aggs": {"debut": {"min": {"field": "@timestamp"}}, "fin": {"max": {"field": "@timestamp"}}}}}}))
    show("Exports", es("POST", "/logs-db.audit-*/_search", {
        "size": 5, "_source": ["@timestamp", "user.name", "source.ip", "destination.ip", "db.statement"],
        "query": {"term": {"event.action": "export"}}}))
    for runs in (500, 100):
        q = ('sequence by user.name with maxspan=10m '
             '[any where event.dataset == "db.audit" and event.action == "select" and object == "clients"] '
             f'with runs={runs} [any where event.dataset == "db.audit" and event.action == "export"]')
        st, r = es("POST", "/logs-db.audit-*/_eql/search", {"query": q, "size": 5})
        if st == 200:
            seqs = r.get("hits", {}).get("sequences", [])
            print(f"\n### EQL runs={runs} -> HTTP 200, {len(seqs)} séquence(s)",
                  [s.get("join_keys") for s in seqs])
        else:
            show(f"EQL runs={runs}", (st, r))
    with open(os.path.join(RULES_DIR, "esql_lecture_puis_export.json"), encoding="utf-8") as f:
        esql = json.load(f)["query"]
    # Sur l'historique on retire la fenêtre de 10 min du planificateur : on vérifie juste la logique.
    show("ES|QL (sur tout l'historique)", es("POST", "/_query?format=json", {"query": esql}))


def load_rules():
    rules = []
    for p in sorted(glob.glob(os.path.join(RULES_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            rules.append((os.path.basename(p), json.load(f)))
    return rules


def deploy():
    for name, rule in load_rules():
        st, r = kb("GET", f"/api/detection_engine/rules?rule_id={rule['rule_id']}")
        if st == 200:
            st, r = kb("PUT", "/api/detection_engine/rules", rule)
            verb = "mise à jour"
        else:
            st, r = kb("POST", "/api/detection_engine/rules", rule)
            verb = "création"
        ok = st == 200
        print(f"{name}: {verb} HTTP {st}" + (f" id={r.get('id')}" if ok else ""))
        if not ok:
            print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])


def manual_run(start, end):
    ids = []
    for rid in RULE_IDS:
        st, r = kb("GET", f"/api/detection_engine/rules?rule_id={rid}")
        if st == 200:
            ids.append(r["id"])
    show("Exécution manuelle", kb("POST", "/api/detection_engine/rules/_bulk_action", {
        "action": "run", "ids": ids, "run": {"start_date": start, "end_date": end}}))


def alerts():
    show("Alertes", kb("POST", "/api/detection_engine/signals/search", {
        "size": 20, "sort": [{"@timestamp": "desc"}],
        "_source": ["@timestamp", "kibana.alert.rule.name", "kibana.alert.severity", "kibana.alert.risk_score",
                    "user.name", "kibana.alert.threshold_result", "kibana.alert.original_time",
                    "kibana.alert.suppression.docs_count", "source.ip", "destination.ip"],
        "query": {"bool": {"filter": [{"terms": {"kibana.alert.rule.rule_id": RULE_IDS}}]}}}))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "deploy":
        deploy()
    elif cmd == "run" and len(sys.argv) == 4:
        manual_run(sys.argv[2], sys.argv[3])
    elif cmd == "alerts":
        alerts()
    else:
        sys.exit(__doc__)
