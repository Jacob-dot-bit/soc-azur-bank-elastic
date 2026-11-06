#!/usr/bin/env python3
r"""Ajoute à fw-01 ce dont le SOAR Shuffle (soar-shuffle-01, 10.40.0.20) a besoin.

Usage : python3 fw_shuffle.py config-actuelle.xml config-nouvelle.xml

À appliquer après fw_zone_soc.py (idempotent : ne fait rien si l'alias SOAR existe déjà).
  - alias SOAR (10.40.0.20) et BLOCKLIST_SOAR (vide, alimenté par Shuffle via l'API) ;
  - BLOCKLIST_SOAR bloqué en tête : en entrée sur le WAN (source) et en sortie de chaque zone (destination) ;
  - SOAR -> fw-01 443 (API OPNsense), -> srv-dc01 22 (OpenSSH), -> db-clients-01 22 (SSH) ;
    ces règles passent avant « SOC -> zones internes interdit » ;
  - WAN : hôte Proxmox -> SOAR 3443 (tunnel SSH vers l'interface Shuffle) ;
  - utilisateur svc-shuffle, sans shell ni accès à l'interface web, avec une clé API limitée aux tables d'alias (Diagnostics: PF Table IP addresses).
La clé API se crée ensuite sur fw-01 (le secret n'est affiché qu'une fois) :
  php -r 'require "/usr/local/opnsense/mvc/script/load_phalcon.php";
          echo json_encode((new OPNsense\Auth\API())->createKey("svc-shuffle"));'
"""
import copy
import sys
import uuid
import xml.etree.ElementTree as ET

src, dst = sys.argv[1:3]
t = ET.parse(src)
r = t.getroot()


def sub(p, tag, text=None, **attr):
    e = ET.SubElement(p, tag, attr)
    if text is not None:
        e.text = text
    return e


al = r.find("OPNsense/Firewall/Alias/aliases")
if any(a.findtext("name") == "SOAR" for a in al):
    sys.exit("alias SOAR déjà présent : rien à faire")


def alias(name, typ, content, descr):
    a = sub(al, "alias", uuid=str(uuid.uuid4()))
    for k, v in [("enabled", "1"), ("name", name), ("type", typ), ("proto", ""), ("interface", ""),
                 ("counters", "0"), ("updatefreq", ""), ("content", "\n".join(content)),
                 ("categories", ""), ("description", descr)]:
        sub(a, k, v)


alias("SOAR", "host", ["10.40.0.20"], "soar-shuffle-01 (Shuffle)")
alias("BLOCKLIST_SOAR", "host", [], "IP bloquees automatiquement par le SOAR")
alias("CIBLES_SOAR_SSH", "host", ["10.10.1.10", "10.10.1.20"], "srv-dc01 + db-clients-01 (actions SOAR en SSH)")

rules = r.find("OPNsense/Firewall/Filter/rules")
existing = list(rules)
tmpl = existing[0]


def mk(action, iface, proto, src, dst, port="", descr=""):
    e = copy.deepcopy(tmpl)
    e.set("uuid", str(uuid.uuid4()))
    for k, v in {"action": action, "interface": iface, "protocol": proto, "source_net": src,
                 "destination_net": dst, "destination_port": port, "destination_not": "0",
                 "log": "1", "description": descr}.items():
        e.find(k).text = v
    return e


blocage = [mk("block", "wan", "any", "BLOCKLIST_SOAR", "any", "", "SOAR : IP bloquee (entree WAN)")]
blocage += [mk("block", z, "any", z, "BLOCKLIST_SOAR", "", f"SOAR : IP bloquee (sortie {z})")
            for z in ("lan", "opt1", "opt2", "opt3", "opt4")]
soar = [
    mk("pass", "opt4", "TCP", "SOAR", "10.40.0.1", "443", "SOAR -> API OPNsense (blocage d'IP)"),
    mk("pass", "opt4", "TCP", "SOAR", "CIBLES_SOAR_SSH", "22", "SOAR -> srv-dc01 / db-clients-01 en SSH (confinement)"),
]
wan_admin = [mk("pass", "wan", "TCP", "192.168.100.1", "SOAR", "3443", "Hote Proxmox -> Shuffle (tunnel SSH)")]

out = blocage[:]
inserted = False
for e in existing:
    if not inserted and e.findtext("interface") == "opt4" and e.findtext("action") == "block":
        out += soar
        inserted = True
    out.append(e)
if not inserted:
    out += soar
out += wan_admin
for x in existing:
    rules.remove(x)
for i, e in enumerate(out, 1):
    e.find("sequence").text = str(i * 10)
    rules.append(e)

# Utilisateur API : pas de connexion interactive, droit unique sur les alias
system = r.find("system")
uids = [int(u.findtext("uid") or 0) for u in system.findall("user")]
u = sub(system, "user", uuid=str(uuid.uuid4()))
for k, v in [("name", "svc-shuffle"), ("descr", "Compte API du SOAR Shuffle"), ("scope", "user"),
             ("password", "*"), ("uid", str(max(uids + [2000]) + 1)), ("shell", "/sbin/nologin"),
             ("priv", "page-diagnostics-tables")]:
    sub(u, k, v)

ET.indent(t, "  ")
t.write(dst, encoding="UTF-8", xml_declaration=True)
print(f"{len(out)} règles, alias + utilisateur svc-shuffle ajoutés -> {dst}")
