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
    g.text("t", 40, 14, 1520, 40,
           ["Azur Bank · Architecture SIEM hybride : le sensible reste sur site, le volume part dans le cloud"],
           "title", size=23)

    # --- On-prem
    g.group("onprem", 40, 70, 860, 680, "ON-PREM · AZUR BANK (siège + N agences reliées en VPN IPsec)", "onprem")

    g.group("crit", 60, 110, 400, 260, "Données critiques : ne quittent jamais la banque", "site", size=13)
    g.box("db", 75, 150, 180, 95, ["db-clients-01", "base clients", "audit pgaudit (use case)"], "dc", size=12)
    g.box("swift", 265, 150, 180, 95, ["Passerelle SWIFT / SEPA", "virements, MT103", "SWIFT CSP"], "dc", size=12)
    g.box("cde", 75, 260, 180, 95, ["Zone cartes (CDE)", "monétique, PAN", "PCI DSS"], "dc", size=12)
    g.box("adbas", 265, 260, 180, 95, ["AD + bastion-01", "comptes, accès", "privilégiés (MFA)"], "adm", size=12)

    g.group("vol", 480, 110, 400, 260, "Sources volumineuses, moins sensibles", "site", size=13)
    g.box("web", 495, 150, 180, 95, ["web-portail-01", "DMZ · nginx / WAF", "portail clients"], "dmz", size=12)
    g.box("fw", 685, 150, 180, 95, ["fw-01 · OPNsense", "flux inter-zones", "seule sortie Internet"], "fw", size=12)
    g.box("ws", 495, 260, 180, 95, ["Postes des agences", "Elastic Defend (EDR)", "+ Sysmon"], "lan", size=12)
    g.box("proxy", 685, 260, 180, 95, ["Proxy, DNS, DHCP", "VPN, Wi-Fi", "(cible)"], "opt", size=12)

    g.group("soc", 60, 420, 820, 315, "Zone SOC (10.40.0.0/24)", "site", size=13)
    g.box("siem", 80, 460, 380, 150,
          ["siem-elk-01 · cluster on-prem",
           "Fleet Server : pilote tous les agents",
           "Elasticsearch : données critiques, 12 mois",
           "Kibana Security : règles + console unique",
           "des analystes (local + cloud via CCS)"], "soc", size=12)
    g.box("ls", 500, 460, 360, 150,
          ["Logstash · seule sortie vers le cloud",
           "envoie : logs moins sensibles + alertes",
           "retire : PAN, IBAN, noms, montants",
           "file persistante : rien n'est perdu",
           "si le lien Internet tombe"], "fw", size=12)
    g.box("shuffle", 80, 630, 380, 85, ["SOAR Shuffle (phase 2)", "lit les alertes, ouvre le case,", "verrouille compte base + AD, bloque l'IP"], "soc", size=12)
    g.text("anan", 500, 630, 360, 85,
           ["Analystes N1 / N2 : une seule console,",
            "une recherche couvre les deux clusters,",
            "sans copier les données"], "note", size=12)

    # --- Cloud
    g.group("cloud", 1040, 70, 520, 450, "ELASTIC CLOUD (région UE)", "cloud")
    g.box("ces", 1065, 115, 470, 110,
          ["Elasticsearch cloud · autoscalé",
           "logs web, firewall, postes, réseau (le gros du volume)",
           "copie des alertes on-prem (survit à une panne du site)"], "cnode", size=12)
    g.box("cdet", 1065, 245, 225, 110, ["Règles sur les", "données cloud", "(SQLi, brute force,", "EDR)"], "soc", size=12)
    g.box("cml", 1310, 245, 225, 110, ["Rétention longue", "à bas coût", "(niveaux froid / gelé)"], "cnode", size=12)
    g.box("cdash", 1065, 375, 470, 120, ["Dashboards direction (COMEX)", "posture, incidents par criticité, MTTD / MTTR",
                                          "consultables hors du réseau de la banque", "sans exposer aucune donnée client"], "soc", size=12)

    # --- Pourquoi pas de duplication
    g.box("nodup", 1040, 545, 520, 205,
          ["Pourquoi on ne duplique pas tout dans le cloud",
           "1. Coût : chaque Go stocké deux fois est payé deux fois",
           "2. Une seule source de vérité : pas de preuve divergente en audit",
           "3. Périmètre PCI DSS / SWIFT CSP réduit au seul site",
           "4. Le CCS donne déjà la vue unique : on interroge,",
           "    on ne recopie pas"], "pillar", size=13, align="left")

    # --- Flux
    g.edge("e_crit", "crit", "siem", [(260, 370), (260, 460)], "data")
    g.edge("e_vol", "vol", "ls", [(680, 370), (680, 460)], "data")
    g.edge("e_alert", "siem", "ls", [(460, 560), (500, 560)], "data")
    g.text("l_alert", 455, 530, 50, 26, ["alertes"], "notedata", size=10)
    g.edge("e_out", "ls", "ces", [(860, 520), (915, 520), (915, 170), (1065, 170)], "data")
    g.text("l_out", 922, 190, 92, 70, ["HTTPS 443", "sortant,", "filtré"], "notedata", size=11)
    g.edge("e_ccs", "siem", "cloud", [(400, 610), (400, 622), (1020, 622), (1020, 205), (1065, 205)], "ctrl", dashed=True)
    g.text("l_ccs", 922, 500, 95, 110, ["Cross-Cluster", "Search", "requêtes à la", "demande,", "TLS sortant"], "notec", size=11)
    g.edge("e_soar", "shuffle", "siem", [(150, 630), (150, 612)], "soar", both=True)

    # --- Piliers
    g.box("p1", 40, 770, 500, 115, ["Stable",
          "collecte, stockage et détection du critique sur site",
          "une coupure cloud n'arrête ni la collecte ni la détection",
          "un seul flux sortant, aucun port entrant"], "pillar", size=13)
    g.box("p2", 550, 770, 500, 115, ["Scalable",
          "les sources qui grossissent le plus partent dans le cloud",
          "le site n'est dimensionné que pour le périmètre critique",
          "nouveau site = agent + jeton d'enrôlement Fleet"], "pillar", size=13)
    g.box("p3", 1060, 770, 500, 115, ["Conforme",
          "cartes, clients et SWIFT restent dans la banque",
          "filtrage à la sortie, TLS, RBAC, région UE (RGPD, DORA)",
          "12 mois de rétention (PCI DSS 10.5.1)"], "pillar", size=13)
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
    g.edge("e_inet", "inet", "vmbr0", [(800, 110), (800, 195)], "net", both=True)
    g.edge("e_n0", "vmbr0", "nat", [(800, 225), (800, 245)], "net")
    g.edge("e_n1", "nat", "vmbr1", [(800, 290), (800, 310)], "net")

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
    g.box("ws", 90, 615, hw, hh, ["ws-agence (VM)", "10.20.30.47 · Windows 11",
                                  "Sysmon + Elastic Defend", "agent : pol-windows"], "node")
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
