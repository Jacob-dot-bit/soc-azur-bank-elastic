#!/usr/bin/env python3
"""Simulateur de passerelle SWIFT (Alliance Gateway) pour le lab Azur Bank.

Envoie des journaux syslog RFC 5424 en TCP à Logstash (siem-elk-01:5514), qui les range
dans logs-swift.gateway-default. Tourne sur bastion-01 (zone ADM, autorisée vers le SOC).

    python3 sim_swift.py              # 5 messages normaux (lancé toutes les 5 min par le timer systemd)
    python3 sim_swift.py --attaque    # + un MT103 de 2,4 M EUR vers un correspondant inconnu
"""
import argparse
import datetime as dt
import random
import socket

DEST = ("10.40.0.10", 5514)
BANQUES = ["DEUTDEFFXXX", "BNPAFRPPXXX", "SOGEFRPPXXX", "COBADEFFXXX", "INGBNL2AXXX", "UBSWCHZH80A"]
OPERATEURS = ["o.martin", "l.petit", "s.leroy"]


def ligne(ts, action, **kv):
    corps = " ".join(f"{k}={v}" for k, v in kv.items())
    return f"<134>1 {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} sag-01 SAG - {action} - {corps}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attaque", action="store_true")
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    msgs = []
    for i in range(a.n):
        typ = random.choice(["MT103", "MT103", "MT202", "MT940"])
        msgs.append(ligne(now, "MSG_OUT" if typ != "MT940" else "MSG_IN", type=typ,
                          ref=f"AZB{now:%Y%m%d}{random.randint(1, 99999):05d}", sender="AZURFRPPXXX",
                          receiver=random.choice(BANQUES), amount=f"{random.uniform(500, 90000):.2f}",
                          currency="EUR", operator=random.choice(OPERATEURS),
                          status=random.choice(["ACK"] * 9 + ["NAK"])))
    if a.attaque:
        # Virement anormal : montant hors norme vers un correspondant absent du référentiel de la banque.
        msgs.append(ligne(now, "MSG_OUT", type="MT103", ref=f"AZB{now:%Y%m%d}99999", sender="AZURFRPPXXX",
                          receiver="KBLXLULLXXX", amount="2400000.00", currency="EUR",
                          operator="c.dupont", status="ACK"))
    with socket.create_connection(DEST, timeout=10) as s:
        s.sendall("".join(msgs).encode())
    print(f"{len(msgs)} message(s) envoyé(s) à {DEST[0]}:{DEST[1]}")


if __name__ == "__main__":
    main()
