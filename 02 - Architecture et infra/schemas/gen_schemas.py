#!/usr/bin/env python3
"""Génère les schémas d'infra Azur Bank au format draw.io (.drawio) et SVG.

Un seul modèle (coordonnées absolues) sert aux deux sorties, pour que le
.drawio modifiable et l'export SVG/PNG restent identiques.
Usage : python3 gen_schemas.py <dossier_sortie>
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "Helvetica, Arial, sans-serif"

STYLES = {
    # nom: (fill, stroke, texte, dashed, rounded)
    "title":   (None, None, "#1B2631", False, False),
    "onprem":  ("#F4F6F8", "#5B6770", "#263238", False, True),
    "cloud":   ("#E8F1FD", "#0B64DD", "#0B3D91", False, True),
    "users":   ("#FAFAFA", "#90A4AE", "#37474F", True, True),
    "site":    ("#FFFFFF", "#90A4AE", "#37474F", False, True),
    "node":    ("#FFFFFF", "#5B6770", "#263238", False, True),
    "cnode":   ("#FFFFFF", "#0B64DD", "#0B3D91", False, True),
    "soc":     ("#E0F7F5", "#00897B", "#004D40", False, True),
    "fw":      ("#FFF3E0", "#E65100", "#BF360C", False, True),
    "opt":     ("#FFFFFF", "#78909C", "#455A64", True, True),
    "ghost":   ("#ECEFF1", "#B0BEC5", "#607D8B", True, True),
    "lan":     ("#EAF6EC", "#2E7D32", "#1B5E20", False, True),
    "dc":      ("#FFF6E5", "#B26A00", "#7A4A00", False, True),
    "dmz":     ("#FDEEEE", "#C62828", "#8E1B1B", False, True),
    "adm":     ("#F1ECFA", "#5E35B1", "#3E2380", False, True),
    "socz":    ("#E0F7F5", "#00897B", "#004D40", False, True),
    "bar":     ("#CFD8DC", "#546E7A", "#263238", False, False),
    "bar1":    ("#FFE0B2", "#E65100", "#BF360C", False, False),
    "pillar":  ("#FFFFFF", "#00897B", "#263238", False, True),
    "notedata": (None, None, "#00695C", False, False),
    "note":    (None, None, "#455A64", False, False),
    "notec":   (None, None, "#0B3D91", False, False),
}

EDGE_COLORS = {"data": "#00897B", "ctrl": "#0B64DD", "net": "#546E7A",
               "soar": "#8E24AA", "user": "#607D8B"}


class Diagram:
    def __init__(self, name, w, h):
        self.name, self.w, self.h = name, w, h
        self.cells = []   # (kind, dict)
        self.nodes = {}

    def box(self, id, x, y, w, h, lines, style="node", kind="node", size=13,
            align="center", valign="middle"):
        d = dict(id=id, x=x, y=y, w=w, h=h, lines=lines, style=style,
                 kind=kind, size=size, align=align, valign=valign)
        self.nodes[id] = d
        self.cells.append(("box", d))
        return d

    def group(self, id, x, y, w, h, title, style, size=15):
        return self.box(id, x, y, w, h, [title], style, kind="group",
                        size=size, align="left", valign="top")

    def text(self, id, x, y, w, h, lines, style="note", size=12, align="center"):
        return self.box(id, x, y, w, h, lines, style, kind="text", size=size,
                        align=align)

    def edge(self, id, src, dst, pts, color="net", dashed=False, both=False):
        self.cells.append(("edge", dict(id=id, src=src, dst=dst, pts=pts,
                                        color=color, dashed=dashed, both=both)))

    # ---------------------------------------------------------------- drawio
    def _label_html(self, d):
        lines = [escape(l) for l in d["lines"]]
        if d["kind"] == "text" and d["style"] != "title":
            return "<br>".join(lines)
        first = f"<b>{lines[0]}</b>"
        if len(lines) == 1:
            return first
        rest = "<br>".join(lines[1:])
        return f"{first}<br><font style=\"font-size:{d['size'] - 1}px\">{rest}</font>"

    def to_drawio(self):
        out = ['<mxfile host="drawio" type="device">',
               f'<diagram id="{self.name}" name="{self.name}">',
               f'<mxGraphModel dx="{self.w}" dy="{self.h}" grid="1" gridSize="10" '
               f'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
               f'pageScale="1" pageWidth="{self.w}" pageHeight="{self.h}" '
               'math="0" shadow="0">',
               '<root><mxCell id="0"/><mxCell id="1" parent="0"/>']
        for kind, d in self.cells:
            if kind == "box":
                fill, stroke, fc, dashed, rounded = STYLES[d["style"]]
                st = ["html=1", "whiteSpace=wrap", f"fontFamily=Helvetica",
                      f"fontSize={d['size']}", f"fontColor={fc}",
                      f"align={d['align']}", f"verticalAlign={d['valign']}"]
                if d["kind"] == "text":
                    st = ["text"] + st + ["strokeColor=none", "fillColor=none"]
                else:
                    st += [f"fillColor={fill}", f"strokeColor={stroke}",
                           f"rounded={1 if rounded else 0}", "arcSize=6",
                           "strokeWidth=" + ("2" if d["kind"] == "group" else "1.5")]
                    if dashed:
                        st.append("dashed=1")
                    if d["kind"] == "group":
                        st += ["spacingLeft=12", "spacingTop=4", "container=0"]
                if d["style"] == "title":
                    st.append("fontStyle=1")
                style = ";".join(st) + ";"
                out.append(
                    f'<mxCell id="{d["id"]}" value="{escape(self._label_html(d), {chr(34): "&quot;"})}" '
                    f'style="{style}" vertex="1" parent="1">'
                    f'<mxGeometry x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" '
                    f'height="{d["h"]}" as="geometry"/></mxCell>')
            else:
                s, t = self.nodes[d["src"]], self.nodes[d["dst"]]
                (sx, sy), (tx, ty) = d["pts"][0], d["pts"][-1]
                st = ["edgeStyle=none", "html=1", "rounded=0", "endArrow=block",
                      "endFill=1", f"strokeColor={EDGE_COLORS[d['color']]}",
                      "strokeWidth=2",
                      f"exitX={(sx - s['x']) / s['w']:.4f}",
                      f"exitY={(sy - s['y']) / s['h']:.4f}", "exitDx=0", "exitDy=0",
                      f"entryX={(tx - t['x']) / t['w']:.4f}",
                      f"entryY={(ty - t['y']) / t['h']:.4f}", "entryDx=0", "entryDy=0"]
                if d["both"]:
                    st += ["startArrow=block", "startFill=1"]
                if d["dashed"]:
                    st.append("dashed=1")
                pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in d["pts"][1:-1])
                arr = f'<Array as="points">{pts}</Array>' if pts else ""
                out.append(
                    f'<mxCell id="{d["id"]}" style="{";".join(st)};" edge="1" '
                    f'parent="1" source="{d["src"]}" target="{d["dst"]}">'
                    f'<mxGeometry relative="1" as="geometry">{arr}</mxGeometry></mxCell>')
        out.append("</root></mxGraphModel></diagram></mxfile>")
        return "\n".join(out)

    # ------------------------------------------------------------------ svg
    def to_svg(self):
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
             f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
             f'font-family="{FONT}">',
             '<defs>']
        for k, c in EDGE_COLORS.items():
            o.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="9" refY="5" '
                     f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                     f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
        o.append('</defs>')
        o.append(f'<rect width="{self.w}" height="{self.h}" fill="#FFFFFF"/>')
        edges = []
        for kind, d in self.cells:
            if kind == "edge":
                edges.append(d)
                continue
            fill, stroke, fc, dashed, rounded = STYLES[d["style"]]
            if d["kind"] != "text":
                sw = 2 if d["kind"] == "group" else 1.5
                r = min(d["w"], d["h"]) * 0.06 if rounded else 0
                da = ' stroke-dasharray="6 4"' if dashed else ""
                o.append(f'<rect x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" '
                         f'height="{d["h"]}" rx="{r:.1f}" fill="{fill}" '
                         f'stroke="{stroke}" stroke-width="{sw}"{da}/>')
            o.append(self._svg_text(d, fc))
        for d in edges:  # arêtes au-dessus des boîtes, comme draw.io
            c = EDGE_COLORS[d["color"]]
            pts = " ".join(f"{x},{y}" for x, y in d["pts"])
            da = ' stroke-dasharray="8 5"' if d["dashed"] else ""
            ms = f' marker-start="url(#a-{d["color"]})"' if d["both"] else ""
            o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" '
                     f'stroke-width="2"{da}{ms} marker-end="url(#a-{d["color"]})"/>')
        o.append("</svg>")
        return "\n".join(o)

    def _svg_text(self, d, color):
        size = d["size"]
        lh = size * 1.3
        lines = d["lines"]
        n = len(lines)
        if d["valign"] == "top":
            y0 = d["y"] + 4 + size + 6
        else:
            y0 = d["y"] + d["h"] / 2 - (n - 1) * lh / 2 + size * 0.35
        if d["align"] == "left":
            x, anchor = d["x"] + 12, "start"
        else:
            x, anchor = d["x"] + d["w"] / 2, "middle"
        parts = []
        for i, l in enumerate(lines):
            plain = d["kind"] == "text" and d["style"] != "title"
            bold = (i == 0 and not plain) or d["style"] == "title"
            fs = size if (i == 0 or plain) else size - 1
            parts.append(f'<text x="{x}" y="{y0 + i * lh:.1f}" text-anchor="{anchor}" '
                         f'font-size="{fs}" font-weight="{"bold" if bold else "normal"}" '
                         f'fill="{color}">{escape(l)}</text>')
        return "\n".join(parts)


# =====================================================================
# 1. Architecture SIEM hybride (slide 16:9)
# =====================================================================
def archi():
    g = Diagram("architecture-hybride", 1600, 900)
    g.text("t", 40, 18, 1520, 40,
           ["Azur Bank · Architecture SIEM hybride : sites On-Prem + Elastic Cloud"],
           "title", size=24)

    # --- On-prem
    g.group("onprem", 40, 80, 720, 670, "ON-PREM · AZUR BANK (1 500 collaborateurs, multi-sites)", "onprem")
    g.group("dcp", 60, 120, 680, 360, "Siège · Datacenter", "site", size=13)
    g.box("srvdc", 80, 160, 200, 80, ["srv-dc01", "Active Directory", "Security + Sysmon"], "dc")
    g.box("db", 300, 160, 200, 80, ["db-clients-01", "PostgreSQL + pgaudit", "base clients (use case)"], "dc")
    g.box("web", 520, 160, 200, 80, ["web-portail-01", "Portail clients nginx", "DMZ · access logs"], "dmz")
    g.box("bastion", 80, 270, 200, 80, ["bastion-01", "SSH + MFA (zone ADM)", "collecteur syslog"], "adm")
    g.box("swift", 300, 270, 200, 80, ["Passerelle SWIFT / SEPA", "syslog → Logstash (simulée)", "SWIFT CSP"], "opt")
    g.box("fw", 520, 270, 200, 80, ["fw-01 · OPNsense", "filtrage inter-zones", "seule sortie Internet"], "fw")
    g.box("siem", 80, 365, 640, 100,
          ["Zone SOC · siem-elk-01 : Fleet Server + Logstash + Elasticsearch + Kibana Security",
           "licence Basic gratuite · les agents (pol-windows, pol-linux-*) parlent à Fleet sur site (8220/9200)",
           "collecte, stockage chaud et détection dans la banque · seul ADM accède à la base clients"],
          "soc", size=12)

    g.group("agences", 60, 500, 330, 230, "Agences (N sites)", "site", size=13)
    g.box("ws", 80, 560, 290, 80, ["Postes guichetiers Windows 11", "Elastic Defend (EDR) + Sysmon", "agent : pol-windows"], "lan")
    g.text("vpn", 80, 650, 290, 60, ["Lien VPN IPsec agence → siège", "les logs sortent par fw-01"], "note", size=12)

    g.group("soar", 410, 500, 330, 230, "SOAR phase 2 (déployé dans le lab)", "site", size=13)
    g.box("shuffle", 430, 560, 290, 80, ["Shuffle (on-prem, zone SOC)", "playbook : case Kibana, compte base", "et AD désactivés, IP bloquée sur fw-01"], "soc")
    g.text("soarn", 430, 650, 290, 60, ["lit les alertes par l'API toutes les minutes", "(licence Basic : pas de webhook)"], "note", size=12)

    # --- Lien
    g.text("link", 770, 380, 145, 110,
           ["HTTPS 443", "sortant uniquement", "TLS chiffré", "aucun port entrant", "côté banque"],
           "notec", size=12)

    # --- Cloud
    g.group("cloud", 920, 80, 640, 470, "ELASTIC CLOUD SERVERLESS · projet Security", "cloud")
    g.box("fleet", 950, 130, 280, 70, ["Fleet (managé)", "politiques et mises à jour des agents"], "cnode")
    g.box("ingest", 950, 240, 280, 70, ["Ingest pipelines", "normalisation ECS (ex. pgaudit → dissect)"], "cnode")
    g.box("es", 950, 350, 280, 90, ["Elasticsearch", "data streams logs-*-banque", "stockage et calcul autoscalés"], "cnode")
    g.box("detect", 1260, 120, 280, 100, ["Moteur de détection", "règles Threshold · EQL · ES|QL", "SIGMA converties", "mapping MITRE ATT&CK"], "soc")
    g.box("cases", 1260, 250, 280, 70, ["Alerts → Cases", "tri N1/N2, 5W, timeline"], "soc")
    g.box("wf", 1260, 350, 280, 70, ["Workflows (SOAR)", "enrichissement, notification"], "soc")
    g.box("dash", 1260, 450, 280, 70, ["Dashboards Kibana Lens", "vue SOC et vue COMEX"], "soc")

    # --- Utilisateurs
    g.group("usr", 920, 580, 640, 170, "Accès Kibana (SSO + RBAC, HTTPS)", "users", size=13)
    g.box("ana", 950, 630, 280, 70, ["Analystes SOC N1 / N2", "triage, investigation"], "node")
    g.box("comex", 1260, 630, 280, 70, ["Direction / COMEX", "KPI risque, conformité"], "node")

    # --- Flux
    g.edge("e_ctrl", "fw", "fleet", [(720, 295), (840, 295), (840, 165), (950, 165)], "ctrl", dashed=True, both=True)
    g.edge("e_data", "fw", "ingest", [(720, 330), (880, 330), (880, 275), (950, 275)], "data")
    g.edge("e_vpn", "ws", "dcp", [(300, 560), (300, 480)], "net", both=True)
    g.edge("e_soar", "shuffle", "cloud", [(720, 600), (850, 600), (850, 530), (920, 530)], "soar", dashed=True)
    g.edge("e_ing", "ingest", "es", [(1090, 310), (1090, 350)], "data")
    g.edge("e_det", "es", "detect", [(1230, 380), (1245, 380), (1245, 170), (1260, 170)], "data")
    g.edge("e_cas", "detect", "cases", [(1400, 220), (1400, 250)], "data")
    g.edge("e_wf", "cases", "wf", [(1400, 320), (1400, 350)], "data")
    g.edge("e_dash", "es", "dash", [(1090, 440), (1090, 485), (1260, 485)], "data")
    g.edge("e_ana", "ana", "cloud", [(1000, 630), (1000, 550)], "user")
    g.edge("e_comex", "comex", "dash", [(1400, 630), (1400, 520)], "user")

    g.text("lg1", 760, 120, 75, 40, ["contrôle", "(Fleet)"], "notec", size=11)
    g.text("lg2", 760, 335, 120, 36, ["données (logs)"], "notedata", size=11)

    # --- Piliers
    g.box("p1", 40, 770, 500, 110, ["Stable",
          "Fleet Server on-prem : la collecte continue même sans le cloud",
          "partie Cloud managée par l'éditeur (SaaS)",
          "agents pilotés via Fleet, aucun flux entrant depuis Internet"], "pillar", size=13)
    g.box("p2", 550, 770, 500, 110, ["Scalable",
          "stockage et calcul autoscalés selon le volume",
          "nouveau site = installer l'agent + jeton d'enrôlement",
          "une politique par rôle, réutilisée partout"], "pillar", size=13)
    g.box("p3", 1060, 770, 500, 110, ["Conforme",
          "TLS en transit, chiffrement au repos, SSO + RBAC",
          "rétention 12 mois des journaux (PCI DSS 10.5.1)",
          "production : région UE (RGPD, DORA)"], "pillar", size=13)
    return g


# =====================================================================
# 2. Réseau du lab Proxmox
# =====================================================================
def lab():
    g = Diagram("lab-proxmox", 1600, 1040)
    g.text("t", 40, 14, 1520, 36, ["Lab Proxmox · réseau et collecte des logs"], "title", size=24)
    g.box("admin", 40, 60, 330, 60, ["Administration", "NetBird → 100.106.21.10 (:8006, SSH)"], "opt")
    g.box("inet", 680, 60, 240, 50, ["Internet"], "node", size=15)
    g.box("elastic", 1180, 50, 380, 70, ["Elastic Cloud Serverless (partie Cloud)", "Fleet + Elasticsearch + Kibana Security"], "cnode")
    g.edge("e_el", "inet", "elastic", [(920, 85), (1180, 85)], "data")
    g.text("l_el", 925, 88, 250, 40, ["HTTPS 443 sortant", "(démo de la partie Cloud)"], "notec", size=12)

    g.group("pve", 40, 150, 1520, 860, "Proxmox VE · serveur dédié OVH (une IP publique)", "onprem")
    g.box("vmbr0", 70, 195, 1460, 30, ["vmbr0 · interface publique OVH"], "bar", size=13)
    g.box("nat", 680, 245, 240, 45, ["Hôte pve : routage + NAT"], "node", size=13)
    g.box("vmbr1", 70, 310, 1460, 30, ["vmbr1 · 192.168.100.0/24 · réseau NAT de l'hôte (passerelle .1)"], "bar1", size=13)
    g.box("old", 1180, 360, 350, 60, ["VMs existantes, inchangées", "105 srv-web-01 · 106 SRV-AD-PinkCastle"], "ghost", size=12)
    g.edge("e_inet", "inet", "vmbr0", [(800, 110), (800, 195)], "net", both=True)
    g.edge("e_n0", "vmbr0", "nat", [(800, 225), (800, 245)], "net")
    g.edge("e_n1", "nat", "vmbr1", [(800, 290), (800, 310)], "net")
    g.edge("e_old", "old", "vmbr1", [(1355, 360), (1355, 340)], "net")

    g.box("fw", 640, 370, 320, 90, ["fw-01 · OPNsense 26.7 (VM)", "WAN 192.168.100.2 · une patte par zone",
                                    "2 vCPU / 2 Go · syslog → bastion-01"], "fw")
    g.edge("e_fw", "vmbr1", "fw", [(800, 340), (800, 370)], "net")

    g.box("z_soc", 70, 352, 540, 128, ["vmbr6 · SOC", "10.40.0.0/24 · gw 10.40.0.1"], "socz", kind="group", size=14,
          align="left", valign="top")
    g.box("siem", 90, 400, 315, 70, ["siem-elk-01 · 10.40.0.10", "Elasticsearch, Kibana, Fleet Server,",
                                     "Logstash 9.5.6 · licence Basic"], "soc", size=12)
    g.box("soar", 415, 400, 175, 70, ["soar-shuffle-01", "10.40.0.20", "Shuffle 2.3 (SOAR)"], "soc", size=12)
    g.edge("f_soc", "fw", "z_soc", [(640, 415), (610, 415)], "net")

    zones = [
        ("lan", 70, "vmbr2 · LAN agences", "10.20.30.0/24 · gw 10.20.30.1"),
        ("dc", 440, "vmbr3 · DC (serveurs)", "10.10.1.0/24 · gw 10.10.1.1"),
        ("dmz", 810, "vmbr4 · DMZ", "10.30.0.0/24 · gw 10.30.0.1"),
        ("adm", 1180, "vmbr5 · ADM (administration)", "10.0.5.0/24 · gw 10.0.5.1"),
    ]
    zy, zw, zh = 540, 350, 330
    for key, x, t1, t2 in zones:
        g.box("z_" + key, x, zy, zw, zh, [t1, t2], key, kind="group", size=14,
              align="left", valign="top")

    hw, hh = 310, 105
    g.box("ws", 90, 615, hw, hh, ["ws-agence (VM, optionnelle)", "10.20.30.47 · Windows 11",
                                  "Sysmon + Elastic Defend", "agent : pol-windows"], "opt")
    g.box("dc01", 460, 615, hw, hh, ["srv-dc01 (VM)", "10.10.1.10 · Windows Server 2025",
                                     "AD azurbank.local · Security + Sysmon", "agent : pol-windows"], "node")
    g.box("db", 460, 740, hw, hh, ["db-clients-01 (LXC Debian 13)", "10.10.1.20 · PostgreSQL + pgaudit",
                                   "logs-db.audit-* (use case exfiltration)", "agent : pol-linux-db"], "node")
    g.box("web", 830, 615, hw, hh, ["web-portail-01 (LXC Debian 13)", "10.30.0.10 · nginx",
                                    "logs nginx.access (SQLi)", "agent : pol-linux-web"], "node")
    g.box("bas", 1200, 615, hw, hh, ["bastion-01 (LXC Debian 13)", "10.0.5.10 · SSH clés + MFA",
                                     "auth.log + syslog fw-01 (UDP 514)", "agent : pol-linux-bastion"], "node")
    g.text("admn", 1200, 740, hw, 105, ["seul point d'entrée vers la zone DC", "(SSH 22, PostgreSQL 5432)",
                                        "brute force simulé depuis Internet"], "note", size=12)

    # fw-01 vers chaque bridge
    g.edge("f_lan", "fw", "z_lan", [(690, 460), (690, 490), (245, 490), (245, 540)], "net")
    g.edge("f_dc", "fw", "z_dc", [(760, 460), (760, 510), (615, 510), (615, 540)], "net")
    g.edge("f_dmz", "fw", "z_dmz", [(840, 460), (840, 510), (985, 510), (985, 540)], "net")
    g.edge("f_adm", "fw", "z_adm", [(910, 460), (910, 490), (1355, 490), (1355, 540)], "net")
    g.edge("e_adm_db", "bas", "db", [(1200, 690), (1170, 690), (1170, 860), (800, 860), (800, 800), (770, 800)], "soar", dashed=True)
    g.text("l_admdb", 830, 834, 330, 22, ["ADM → DC : 22 / 5432 uniquement"], "note", size=11)

    g.box("rules", 70, 885, 1460, 115, [
        "Flux autorisés par fw-01 (tout le reste est refusé et journalisé)",
        "LAN → DMZ : 443  ·  LAN → DC : services AD (53, 88, 389, 445)  ·  ADM → DC : 22, 5432 (seul accès à la base clients)",
        "Toutes zones → siem-elk-01 : 8220 (Fleet Server) et 9200 (Elasticsearch)  ·  SOC → zones internes : refusé  ·  fw-01 → bastion-01 : syslog UDP 514",
        "SOAR → fw-01 : 443 (API, blocage d'IP)  ·  SOAR → srv-dc01, db-clients-01 : 22 (confinement)  ·  bastion → Logstash : 5514 (SWIFT simulé)",
        "Hôte Proxmox → SIEM 22/5601, SOAR 3443 (tunnels SSH)  ·  LAN, DC, DMZ, SOC → Internet : 80/443 uniquement"],
        "pillar", size=13)
    return g


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for g in (archi(), lab()):
        (out / f"{g.name}.drawio").write_text(g.to_drawio(), encoding="utf-8")
        (out / f"{g.name}.svg").write_text(g.to_svg(), encoding="utf-8")
        print("ok", g.name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "schemas")
