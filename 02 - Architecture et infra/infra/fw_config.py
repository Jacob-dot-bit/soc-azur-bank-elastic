#!/usr/bin/env python3
"""Génère la config OPNsense de fw-01 (Azur Bank) à partir de la config par défaut."""
import sys, uuid, copy, crypt
import xml.etree.ElementTree as ET

src, dst, rootpw = sys.argv[1], sys.argv[2], sys.argv[3]
t = ET.parse(src); r = t.getroot()
def sub(p, tag, text=None, **attr):
    e = ET.SubElement(p, tag, attr)
    if text is not None: e.text = text
    return e

r.find("system/hostname").text = "fw-01"
r.find("system/domain").text = "azurbank.local"
for u in r.findall("system/user"):
    if u.findtext("name") == "root":
        u.find("password").text = crypt.crypt(rootpw, crypt.mksalt(crypt.METHOD_SHA512))
ssh = r.find("system/ssh")
for k, v in {"enabled": "enabled", "permitrootlogin": "1", "passwordauth": "1"}.items():
    sub(ssh, k, v)
dns = r.find("system")
for d in ("1.1.1.1", "9.9.9.9"):
    sub(dns, "dnsserver", d)

ifs = r.find("interfaces")
wan, lan = ifs.find("wan"), ifs.find("lan")
wan.find("if").text = "vtnet0"; wan.find("ipaddr").text = "192.168.100.2"
wan.find("ipaddrv6").text = ""; wan.find("subnet").text = "24"; wan.find("gateway").text = "WAN_GW"
wan.find("blockpriv").text = "0"; wan.find("blockbogons").text = "0"
sub(wan, "descr", "WAN")
lan.find("if").text = "vtnet1"; lan.find("ipaddr").text = "10.20.30.1"
for tag in ("ipaddrv6", "subnetv6", "track6-interface", "track6-prefix-id"):
    e = lan.find(tag); lan.remove(e)
sub(lan, "descr", "LAN")
zones = {"opt1": ("DC", "vtnet2", "10.10.1.1"), "opt2": ("DMZ", "vtnet3", "10.30.0.1"), "opt3": ("ADM", "vtnet4", "10.0.5.1")}
lo0 = ifs.find("lo0"); ifs.remove(lo0)
for name, (descr, nic, ip) in zones.items():
    z = sub(ifs, name); sub(z, "if", nic); sub(z, "descr", descr); sub(z, "enable", "1")
    sub(z, "ipaddr", ip); sub(z, "subnet", "24"); sub(z, "spoofmac", "")
ifs.append(lo0)

# Pas de DHCP (adresses statiques), on retire les plages dnsmasq
dm = r.find("dnsmasq")
for d in dm.findall("dhcp_ranges"): dm.remove(d)

gw = r.find("OPNsense/Gateways")
g = sub(gw, "gateway_item", uuid=str(uuid.uuid4()))
for k, v in [("disabled", "0"), ("name", "WAN_GW"), ("descr", "Passerelle hote Proxmox (vmbr1)"), ("interface", "wan"),
             ("ipprotocol", "inet"), ("gateway", "192.168.100.1"), ("defaultgw", "1"), ("fargw", "0"),
             ("monitor_disable", "1"), ("monitor_noroute", "0"), ("monitor", ""), ("force_down", "0"),
             ("priority", "255"), ("weight", "1"), ("latencylow", ""), ("latencyhigh", ""), ("losslow", ""),
             ("losshigh", ""), ("interval", ""), ("time_period", ""), ("loss_interval", ""), ("data_length", "")]:
    sub(g, k, v)

al = r.find("OPNsense/Firewall/Alias/aliases")
def alias(name, typ, content, descr):
    a = sub(al, "alias", uuid=str(uuid.uuid4()))
    for k, v in [("enabled", "1"), ("name", name), ("type", typ), ("proto", ""), ("interface", ""), ("counters", "0"),
                 ("updatefreq", ""), ("content", "\n".join(content)), ("categories", ""), ("description", descr)]:
        sub(a, k, v)
alias("RESEAUX_PRIVES", "network", ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"], "RFC1918 (pour isoler Internet)")
alias("WEB", "port", ["80", "443"], "HTTP/HTTPS")
alias("SRV_DC01", "host", ["10.10.1.10"], "Controleur de domaine")
alias("DB_CLIENTS", "host", ["10.10.1.20"], "Base clients PostgreSQL")

rules = r.find("OPNsense/Firewall/Filter/rules")
tmpl = rules.find("rule")
for x in list(rules): rules.remove(x)
seq = [0]
def rule(action, iface, proto, src, dst, port="", descr="", dnot=False):
    seq[0] += 10
    e = copy.deepcopy(tmpl); e.set("uuid", str(uuid.uuid4()))
    vals = {"sequence": str(seq[0]), "action": action, "interface": iface, "protocol": proto, "source_net": src,
            "destination_net": dst, "destination_port": port, "destination_not": "1" if dnot else "0",
            "log": "1", "description": descr}
    for k, v in vals.items(): e.find(k).text = v
    rules.append(e)
gwip = {"lan": "10.20.30.1", "opt1": "10.10.1.1", "opt2": "10.30.0.1", "opt3": "10.0.5.1"}
for z in gwip:
    rule("pass", z, "TCP/UDP", z, gwip[z], "53", f"{z}: DNS vers fw-01")
    rule("pass", z, "UDP", z, "any", "123", f"{z}: NTP", dnot=False)
rule("block", "lan", "any", "lan", "DB_CLIENTS", "", "LAN -> base clients interdit (seul ADM)")
rule("pass", "lan", "any", "lan", "SRV_DC01", "", "LAN -> AD (authentification postes)")
rule("pass", "lan", "TCP", "lan", "opt2", "WEB", "LAN -> portail DMZ")
rule("block", "opt2", "any", "opt2", "RESEAUX_PRIVES", "", "DMZ -> zones internes interdit")
rule("block", "opt1", "any", "opt1", "RESEAUX_PRIVES", "", "DC -> autres zones interdit")
rule("pass", "opt3", "any", "opt3", "any", "", "ADM -> tout (administration, seul acces a la base)")
for z in ("lan", "opt1", "opt2"):
    rule("pass", z, "TCP", z, "RESEAUX_PRIVES", "WEB", f"{z}: sortie Internet HTTP/HTTPS (agents, apt)", dnot=True)

sl = r.find("OPNsense/Syslog/destinations")
d = sub(sl, "destination", uuid=str(uuid.uuid4()))
for k, v in [("enabled", "1"), ("transport", "udp4"), ("program", ""), ("level", ""), ("facility", ""),
             ("hostname", "10.0.5.10"), ("certificate", ""), ("port", "514"), ("rfc5424", "0"),
             ("description", "bastion-01 (Elastic Agent, Custom UDP)")]:
    sub(d, k, v)

ET.indent(t, "  ")
t.write(dst, encoding="UTF-8", xml_declaration=True)
