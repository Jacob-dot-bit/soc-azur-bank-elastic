#!/usr/bin/env python3
"""Crée le tableau de bord direction (COMEX) dans Kibana et l'exporte en ndjson.

Usage (sur siem-elk-01) :
    export KB_URL=https://10.40.0.10:5601 ES_API_KEY=... ES_CA=/root/elastic/pki/ca/ca.crt
    python3 creer_dashboard_comex.py dashboard_comex.ndjson

Contenu : une vue de données sur les alertes du SIEM, avec quatre champs calculés (runtime fields) :
    mttd_minutes   délai entre l'événement d'origine et l'alerte (temps de détection)
    mttr_minutes   délai entre l'alerte et sa prise en charge (statut passé à acknowledged ou closed)
    conformite     exigences réglementaires portées par les étiquettes de la règle (PCI DSS..., SWIFT CSP...)
    faux_positif   « oui » si l'analyste a étiqueté l'alerte « faux-positif » à la clôture
puis neuf visualisations Lens réunies dans le dashboard « Azur Bank - Tableau de bord direction (SOC) ».
"""
import json
import os
import ssl
import sys
import urllib.request
import uuid
import urllib.error

KB = os.environ["KB_URL"].rstrip("/")
H = {"Authorization": "ApiKey " + os.environ["ES_API_KEY"], "kbn-xsrf": "true"}
CTX = ssl.create_default_context(cafile=os.environ.get("ES_CA") or None)
OUT = sys.argv[1] if len(sys.argv) > 1 else "dashboard_comex.ndjson"

# Identifiants fixes : relancer le script met à jour les mêmes objets au lieu d'en créer de nouveaux
NS = uuid.UUID("6f1c2a52-0b5e-4d3a-9a51-7d2c3e4f5a60")
def oid(nom): return str(uuid.uuid5(NS, nom))

DV = oid("data-view-alertes")
SANS_BB = "not kibana.alert.building_block_type : *"  # les alertes « building block » ne sont pas des incidents

def ms(champ): return f"doc['{champ}'].value.toInstant().toEpochMilli()"
def a(champ): return f"doc.containsKey('{champ}') && doc['{champ}'].size() > 0"
runtime = {
    "mttd_minutes": {"type": "double", "script": {"source":
        f"if ({a('kibana.alert.original_time')}) {{ emit(({ms('@timestamp')} - {ms('kibana.alert.original_time')}) / 60000.0); }}"}},
    "mttr_minutes": {"type": "double", "script": {"source":
        f"if ({a('kibana.alert.workflow_status_updated_at')} && {a('kibana.alert.workflow_status')} "
        f"&& doc['kibana.alert.workflow_status'].value != 'open') "
        f"{{ emit(({ms('kibana.alert.workflow_status_updated_at')} - {ms('@timestamp')}) / 60000.0); }}"}},
    "conformite": {"type": "keyword", "script": {"source":
        "if (doc.containsKey('kibana.alert.rule.tags')) { for (def t : doc['kibana.alert.rule.tags']) "
        "{ if (t.startsWith('PCI DSS') || t.startsWith('SWIFT CSP')) { emit(t); } } }"}},
    "faux_positif": {"type": "keyword", "script": {"source":
        "boolean fp = false; if (doc.containsKey('kibana.alert.workflow_tags')) { for (def t : doc['kibana.alert.workflow_tags']) "
        "{ if (t == 'faux-positif') { fp = true; } } } emit(fp ? 'oui' : 'non');"}},
}
objets = [{"type": "index-pattern", "id": DV, "attributes": {
    "title": ".alerts-security.alerts-default", "name": "Alertes SOC Azur Bank", "timeFieldName": "@timestamp",
    "allowHidden": True, "runtimeFieldMap": json.dumps(runtime)}, "references": []}]


def col_count(label, kql=None):
    c = {"label": label, "customLabel": True, "dataType": "number", "operationType": "count", "isBucketed": False,
         "scale": "ratio", "sourceField": "___records___"}
    if kql:
        c["filter"] = {"query": kql, "language": "kuery"}
    return c

def col_avg(label, champ):
    return {"label": label, "customLabel": True, "dataType": "number", "operationType": "average", "isBucketed": False,
            "scale": "ratio", "sourceField": champ, "params": {"format": {"id": "number", "params": {"decimals": 1}}}}

def col_terms(label, champ, tri, taille=10):
    return {"label": label, "customLabel": True, "dataType": "string", "operationType": "terms", "scale": "ordinal",
            "sourceField": champ, "isBucketed": True,
            "params": {"size": taille, "orderBy": {"type": "column", "columnId": tri}, "orderDirection": "desc",
                       "otherBucket": False, "missingBucket": False}}

def col_jour():
    return {"label": "Jour", "customLabel": True, "dataType": "date", "operationType": "date_histogram",
            "sourceField": "@timestamp", "isBucketed": True, "scale": "interval", "params": {"interval": "1d"}}

def lens(nom, titre, vis_type, colonnes, ordre, visualisation):
    i = oid("lens-" + nom)
    objets.append({"type": "lens", "id": i, "attributes": {
        "title": titre, "description": "", "visualizationType": vis_type,
        "state": {"datasourceStates": {"formBased": {"layers": {"l1": {
                      "columns": colonnes, "columnOrder": ordre, "incompleteColumns": {}}}}},
                  "visualization": visualisation, "query": {"query": SANS_BB, "language": "kuery"}, "filters": [],
                  "internalReferences": [], "adHocDataViews": {}}},
        "references": [{"type": "index-pattern", "id": DV, "name": "indexpattern-datasource-layer-l1"}],
        # format Lens actuel (formBased) : on indique la version pour que Kibana ne rejoue pas les migrations 7.x
        "typeMigrationVersion": "8.9.0", "coreMigrationVersion": "8.8.0"})
    return i

def metrique(nom, titre, colonne):
    return lens(nom, titre, "lnsMetric", {"c1": colonne}, ["c1"],
                {"layerId": "l1", "layerType": "data", "metricAccessor": "c1"})

def barres(nom, titre, x, y, split=None, horizontal=False):
    cols = {"x": x, "y": y}; ordre = ["x"]
    if split: cols["s"] = split; ordre.append("s")
    ordre.append("y")
    couche = {"layerId": "l1", "layerType": "data", "seriesType": "bar_horizontal_stacked" if horizontal else "bar_stacked",
              "xAccessor": "x", "accessors": ["y"]}
    if split: couche["splitAccessor"] = "s"
    return lens(nom, titre, "lnsXY", cols, ordre, {
        "legend": {"isVisible": True, "position": "right"}, "valueLabels": "show",
        "preferredSeriesType": couche["seriesType"], "layers": [couche]})

def tableau(nom, titre, cols, ordre):
    return lens(nom, titre, "lnsDatatable", cols, ordre,
                {"layerId": "l1", "layerType": "data", "columns": [{"columnId": c} for c in ordre]})

panneaux = [
    # (id, x, y, w, h) sur une grille de 48 colonnes
    (metrique("ouvertes", "Incidents ouverts (à traiter)", col_count("Incidents ouverts (à traiter)", "kibana.alert.workflow_status : \"open\"")), 0, 0, 12, 7),
    (metrique("critiques", "Incidents critiques (période)", col_count("Incidents critiques (période)", "kibana.alert.severity : \"critical\"")), 12, 0, 12, 7),
    (metrique("mttd", "MTTD : délai moyen de détection (min)", col_avg("MTTD : délai moyen de détection (min)", "mttd_minutes")), 24, 0, 12, 7),
    (metrique("mttr", "MTTR : délai moyen de prise en charge (min)", col_avg("MTTR : délai moyen de prise en charge (min)", "mttr_minutes")), 36, 0, 12, 7),
    (barres("criticite", "Incidents par criticité et par statut",
            col_terms("Criticité", "kibana.alert.severity", "y", 4), col_count("Incidents"),
            col_terms("Statut", "kibana.alert.workflow_status", "y", 3)), 0, 7, 24, 13),
    (barres("jour", "Incidents par jour et par scénario", col_jour(), col_count("Incidents"),
            col_terms("Règle", "kibana.alert.rule.name", "y", 8)), 24, 7, 24, 13),
    (barres("conformite", "Incidents par exigence réglementaire (PCI DSS, SWIFT CSP)",
            col_terms("Exigence", "conformite", "y", 10), col_count("Incidents"), horizontal=True), 0, 20, 24, 13),
    (barres("fp", "Faux positifs déclarés à la clôture",
            col_terms("Faux positif", "faux_positif", "y", 2), col_count("Incidents"),
            col_terms("Règle", "kibana.alert.rule.name", "y", 8)), 24, 20, 24, 13),
    (tableau("comptes", "Comptes et sources les plus concernés",
             {"u": col_terms("Compte", "user.name", "n", 10), "n": col_count("Incidents"),
              "r": {"label": "Risque max", "customLabel": True, "dataType": "number", "operationType": "max",
                    "sourceField": "kibana.alert.risk_score", "isBucketed": False, "scale": "ratio"}},
             ["u", "n", "r"]), 0, 33, 48, 12),
]
panels, refs = [], []
for k, (i, x, y, w, h) in enumerate(panneaux):
    p = f"p{k}"
    conf = {"enhancements": {}}
    if k < 4:
        conf["hidePanelTitles"] = True  # les tuiles chiffrées portent déjà leur libellé
    panels.append({"panelIndex": p, "gridData": {"x": x, "y": y, "w": w, "h": h, "i": p}, "type": "lens",
                   "embeddableConfig": conf, "panelRefName": "panel_" + p})
    refs.append({"name": "panel_" + p, "type": "lens", "id": i})
objets.append({"type": "dashboard", "id": oid("dashboard-comex"), "attributes": {
    "title": "Azur Bank - Tableau de bord direction (SOC)",
    "description": "Vue COMEX : posture (incidents ouverts, critiques), criticité, conformité PCI DSS et SWIFT CSP, "
                   "délais de détection et de prise en charge (MTTD, MTTR), faux positifs.",
    "panelsJSON": json.dumps(panels), "timeRestore": True, "timeFrom": "now-7d", "timeTo": "now",
    "refreshInterval": {"pause": False, "value": 60000},
    "optionsJSON": json.dumps({"useMargins": True, "syncColors": True, "hidePanelTitles": False}),
    "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}},
    "references": refs})

# Import (écrase les versions précédentes), puis export propre de Kibana vers le fichier ndjson
ndjson = "\n".join(json.dumps(o, ensure_ascii=False) for o in objets) + "\n"
bord = "----azurbank" + uuid.uuid4().hex
corps = (f"--{bord}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"comex.ndjson\"\r\n"
         f"Content-Type: application/ndjson\r\n\r\n{ndjson}\r\n--{bord}--\r\n").encode()
req = urllib.request.Request(KB + "/api/saved_objects/_import?overwrite=true", data=corps, method="POST",
                             headers=dict(H, **{"Content-Type": "multipart/form-data; boundary=" + bord}))
try:
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        res = json.load(r)
except urllib.error.HTTPError as e:
    sys.exit(e.read().decode()[:1500])
print("import :", "succès" if res.get("success") else res.get("errors"), f"({res.get('successCount')} objets)")

req = urllib.request.Request(KB + "/api/saved_objects/_export", method="POST",
                             data=json.dumps({"objects": [{"type": "dashboard", "id": oid("dashboard-comex")}],
                                              "includeReferencesDeep": True}).encode(),
                             headers=dict(H, **{"Content-Type": "application/json"}))
with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
    open(OUT, "wb").write(r.read())
print("export :", OUT)
print("dashboard :", f"{KB}/app/dashboards#/view/{oid('dashboard-comex')}")
