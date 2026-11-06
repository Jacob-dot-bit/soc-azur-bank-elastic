#!/usr/bin/env python3
"""Schéma du playbook Shuffle « Azur Bank - Réponse exfiltration et fraude SWIFT » (drawio + svg).

Reprend la structure du workflow réel (déclencheur, 4 nœuds, condition sur le 1er lien), lue dans Shuffle le 6/11/2026.
Réutilise le moteur de dessin de « 02 - Architecture et infra/schemas/gen_schemas.py ».
Usage : python3 gen_playbook.py [dossier_sortie]
"""
import importlib.util
import sys
from pathlib import Path

ici = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gen_schemas", ici.parent.parent / "02 - Architecture et infra" / "schemas" / "gen_schemas.py")
gs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gs)


def playbook():
    g = gs.Diagram("playbook-shuffle", 1600, 960)
    g.text("t", 40, 16, 1520, 40, ["Playbook SOAR Shuffle · Réponse à l'exfiltration de la base clients (et fraude SWIFT)"], "title", size=22)
    g.text("st", 40, 56, 1520, 24, ["workflow « Azur Bank - Réponse exfiltration et fraude SWIFT » sur soar-shuffle-01 (10.40.0.20), 4 nœuds Python, exécuté toutes les 60 s"], "note", size=13)

    # --- Chaîne principale
    y, h = 150, 96
    g.box("trig", 40, y, 190, h, ["Déclencheur", "planification", "toutes les 60 s"], "opt")
    g.box("n1", 290, y, 230, h, ["1 · lire_alertes", "alertes ouvertes, non", "étiquetées soar-traite"], "soc")
    g.box("cond", 580, y + 8, 170, h - 16, ["nb > 0 ?", "(condition du lien)"], "fw")
    g.box("n2", 810, y, 230, h, ["2 · ouvrir_case", "un case Kibana par compte", "alertes attachées"], "soc")
    g.box("n3", 1090, y, 230, h, ["3 · reponse", "confinement", "(si actions_actives = oui)"], "soc")
    g.box("n4", 1370, y, 190, h, ["4 · cloturer", "bilan dans le case,", "alertes acquittées"], "soc")
    g.box("fin", 580, y + 150, 170, 50, ["fin : rien à traiter"], "ghost", size=12)
    m = y + h // 2
    g.edge("e0", "trig", "n1", [(230, m), (290, m)], "ctrl")
    g.edge("e1", "n1", "cond", [(520, m), (580, m)], "ctrl")
    g.edge("e2", "cond", "n2", [(750, m), (810, m)], "ctrl")
    g.edge("e3", "n2", "n3", [(1040, m), (1090, m)], "ctrl")
    g.edge("e4", "n3", "n4", [(1320, m), (1370, m)], "ctrl")
    g.edge("e5", "cond", "fin", [(665, y + h - 8), (665, y + 150)], "net", dashed=True)
    g.text("loui", 752, m - 30, 56, 20, ["oui"], "notec", size=12)
    g.text("lnon", 672, y + 108, 50, 20, ["non"], "note", size=12)

    # --- Systèmes appelés
    g.group("siem", 290, 380, 750, 190, "", "cloud", size=13)
    g.text("siemt", 550, 430, 230, 110, ["SIEM on-prem", "siem-elk-01 (10.40.0.10)", "compte svc-shuffle,", "rôle soar_shuffle"], "notec", size=13)
    g.box("es", 310, 425, 230, 120, ["Elasticsearch :9200", "recherche dans", ".alerts-security.alerts-*", "règles du use case + SWIFT"], "cnode", size=12)
    g.box("cases", 790, 425, 230, 120, ["Kibana :5601", "API Cases : case,", "alertes, commentaires", "API alertes : statut, étiquettes"], "cnode", size=12)
    g.edge("a1", "n1", "es", [(405, y + h), (405, 425)], "data", both=True)
    g.edge("a2", "n2", "cases", [(925, y + h), (925, 425)], "data")
    g.edge("a4", "n4", "cases", [(1548, y + h), (1548, 600), (1005, 600), (1005, 545)], "data")

    g.group("cibles", 1090, 290, 440, 280, "Confinement", "site", size=13)
    g.box("db", 1105, 330, 410, 66, ["db-clients-01 · SSH :22, svc-shuffle (clé)", "soar-verrou-db.sh : NOLOGIN, sessions coupées"], "dc", size=12)
    g.box("ad", 1105, 408, 410, 66, ["srv-dc01 · SSH :22, svc.shuffle", "(Opérateurs de compte) : Disable-ADAccount"], "dc", size=12)
    g.box("fw", 1105, 486, 410, 66, ["fw-01 · API :443, clé svc-shuffle", "IP externe ajoutée à BLOCKLIST_SOAR"], "fw", size=12)
    g.edge("a3", "n3", "db", [(1205, y + h), (1205, 330)], "soar")

    # --- Mesures réelles
    g.box("mes", 40, 630, 1520, 140, [
        "Exécution réelle du 6 novembre 2026 (heure de Paris), incident c_dupont",
        "18:16:11 export de la table clients · 18:16:26 alerte EQL · 18:16:35 alerte Threshold",
        "18:17:13 case ouvert (nœud 2) · 18:17:16 rôle c_dupont en NOLOGIN · 18:17:17 c.dupont désactivé dans l'AD (4725 par svc.shuffle)",
        "18:17:19 alertes acquittées (nœud 4) · détection en 15 s, confinement 50 s après la première alerte, sans intervention humaine"], "pillar", size=13)
    g.box("leg", 40, 800, 1520, 120, [
        "Garde-fous",
        "mode simulation : variable actions_actives = non (case et acquittement, sans confinement) · IP interne jamais bloquée",
        "rôle postgres et comptes svc_* protégés · comptes administrateurs AD hors de portée (Opérateurs de compte)",
        "secrets dans les variables du workflow, pas dans le code · remise à zéro après une démo : reinitialiser_demo.sh"], "pillar", size=13)
    g.text("lg1", 40, 268, 230, 20, ["→ flux du workflow"], "notec", size=12)
    g.text("lg2", 40, 290, 230, 20, ["→ appels API / SSH"], "notedata", size=12)
    return g


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ici)
    out.mkdir(parents=True, exist_ok=True)
    g = playbook()
    (out / f"{g.name}.drawio").write_text(g.to_drawio(), encoding="utf-8")
    (out / f"{g.name}.svg").write_text(g.to_svg(), encoding="utf-8")
    print("ok", g.name)
