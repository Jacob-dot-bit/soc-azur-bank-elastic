#!/usr/bin/env python3
"""Ajoute la zone SOC (siem-elk-01) à la config OPNsense de fw-01.

Usage : python3 fw_zone_soc.py config-actuelle.xml config-nouvelle.xml

À appliquer sur une config déjà générée par fw_config.py (idempotent : ne fait rien
si l'interface SOC existe déjà). Ce que le script ajoute :
  - interface opt4 « SOC » sur vtnet5 (bridge Proxmox vmbr6), 10.40.0.1/24 ;
  - alias SIEM (10.40.0.10) et PORTS_AGENTS (8220 Fleet Server, 9200 Elasticsearch) ;
  - chaque zone (LAN, DC, DMZ, ADM) -> SIEM en 8220/9200 : les agents parlent au Fleet on-prem ;
  - SOC -> DNS/NTP de fw-01, SOC -> Internet en 80/443 (paquets, artefacts Elastic) ;
  - WAN : l'hôte Proxmox (192.168.100.1) -> SIEM en 22/5601 (tunnel SSH vers Kibana) ;
  - SOC -> zones internes refusé (le SIEM reçoit, il n'initie rien).
Les règles des zones sont insérées avant les règles « -> zones internes interdit ».
"""
import copy
import sys
import uuid
import xml.etree.ElementTree as ET

src, dst = sys.argv[1], sys.argv[2]
t = ET.parse(src)
r = t.getroot()


def sub(p, tag, text=None, **attr):
    e = ET.SubElement(p, tag, attr)
    if text is not None:
        e.text = text
    return e


ifs = r.find("interfaces")
if ifs.find("opt4") is not None:
    sys.exit("opt4 existe déjà : rien à faire")

lo0 = ifs.find("lo0")
ifs.remove(lo0)
z = sub(ifs, "opt4")
for k, v in [("if", "vtnet5"), ("descr", "SOC"), ("enable", "1"), ("ipaddr", "10.40.0.1"),
             ("subnet", "24"), ("spoofmac", "")]:
    sub(z, k, v)
ifs.append(lo0)

al = r.find("OPNsense/Firewall/Alias/aliases")


def alias(name, typ, content, descr):
    a = sub(al, "alias", uuid=str(uuid.uuid4()))
    for k, v in [("enabled", "1"), ("name", name), ("type", typ), ("proto", ""), ("interface", ""),
                 ("counters", "0"), ("updatefreq", ""), ("content", "\n".join(content)),
                 ("categories", ""), ("description", descr)]:
        sub(a, k, v)


alias("SIEM", "host", ["10.40.0.10"], "siem-elk-01 (Elasticsearch, Kibana, Fleet Server)")
alias("PORTS_AGENTS", "port", ["8220", "9200"], "Fleet Server + Elasticsearch (Elastic Agent)")
alias("PORTS_ADMIN_SIEM", "port", ["22", "5601"], "SSH + Kibana")

rules = r.find("OPNsense/Firewall/Filter/rules")
existing = list(rules)
tmpl = existing[0]


def mk(action, iface, proto, src, dst, port="", descr="", dnot=False):
    e = copy.deepcopy(tmpl)
    e.set("uuid", str(uuid.uuid4()))
    vals = {"action": action, "interface": iface, "protocol": proto, "source_net": src,
            "destination_net": dst, "destination_port": port, "destination_not": "1" if dnot else "0",
            "log": "1", "description": descr}
    for k, v in vals.items():
        e.find(k).text = v
    return e


agents = [mk("pass", zn, "TCP", zn, "SIEM", "PORTS_AGENTS", f"{zn}: Elastic Agent -> SIEM (Fleet 8220, ES 9200)")
          for zn in ("lan", "opt1", "opt2")]
soc = [
    mk("pass", "opt4", "TCP/UDP", "opt4", "10.40.0.1", "53", "opt4: DNS vers fw-01"),
    mk("pass", "opt4", "UDP", "opt4", "any", "123", "opt4: NTP"),
    mk("pass", "opt4", "TCP", "opt4", "RESEAUX_PRIVES", "WEB", "opt4: sortie Internet HTTP/HTTPS (apt, artefacts)", dnot=True),
    mk("block", "opt4", "any", "opt4", "RESEAUX_PRIVES", "", "SOC -> zones internes interdit (le SIEM recoit)"),
    mk("pass", "wan", "TCP", "192.168.100.1", "SIEM", "PORTS_ADMIN_SIEM", "Hote Proxmox -> SIEM (tunnel SSH vers Kibana)"),
]

# Ordre : règles existantes, agents insérés juste avant le premier « block ... RESEAUX_PRIVES »
out = []
inserted = False
for e in existing:
    if not inserted and e.findtext("action") == "block" and e.findtext("destination_net") == "RESEAUX_PRIVES":
        out += agents
        inserted = True
    out.append(e)
if not inserted:
    out += agents
out += soc
for x in existing:
    rules.remove(x)
for i, e in enumerate(out, 1):
    e.find("sequence").text = str(i * 10)
    rules.append(e)

ET.indent(t, "  ")
t.write(dst, encoding="UTF-8", xml_declaration=True)
print(f"{len(out)} règles, zone SOC ajoutée -> {dst}")
