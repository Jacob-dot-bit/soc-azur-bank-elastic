#!/usr/bin/env python3
"""Simulateur de virements SEPA sortants (SCT et SCT Inst) pour le lab Azur Bank.

Joue le rôle du hub de paiements SEPA de la banque : chaque virement émis par un client produit une ligne
syslog RFC 5424 envoyée en TCP à Logstash (siem-elk-01:5515), qui l'enrichit et la range dans
logs-sepa.transfer-default. Tourne sur bastion-01 (zone ADM, autorisée vers le SOC), comme sim_swift.py.

    python3 sim_sepa.py                       # 6 virements normaux (lancé toutes les 5 min par le timer systemd)
    python3 sim_sepa.py --fraude              # + un SCT Inst de 48 000 EUR vers un compte inconnu (compte mule)
    python3 sim_sepa.py -n 0 --normal-unique  # un seul virement normal : 1 250 EUR en SCT vers un bénéficiaire connu
    python3 sim_sepa.py --date 2026-11-13T22:00:00Z --fraude -n 0   # horodatage imposé (tests rejoués)

Les IBAN sont fictifs (clé de contrôle valide). Les bénéficiaires habituels de chaque client sont aussi dans le
référentiel de Logstash (infra/logstash/sepa-beneficiaires.yml) : tout autre IBAN est un nouveau bénéficiaire.
"""
import argparse
import datetime as dt
import random
import socket

DEST = ("10.40.0.10", 5515)

# Client (identifiant banque en ligne) -> IBAN du compte et bénéficiaires habituels.
CLIENTS = {
    "C100231": ("FR6130004012344976713868333", ["FR3795460402193004111438338", "FR6694011345591914919529278", "FR5338037486216596331210926"]),
    "C100587": ("FR0930004012341922005063543", ["FR2169122672473125718220942", "FR2356627406748625716087282", "FR5966305979139774541851650"]),
    "C101044": ("FR5130004012342569918814254", ["FR9787945930714859320682167", "FR8182643901097070873463996", "FR2968117802514941334182535"]),
    "C102310": ("FR1930004012347949004521855", ["FR4643202586424633309984387", "FR8946718618723099924373483", "FR9474337820938832064846440"]),
    "C103877": ("FR8630004012343957781277856", ["FR1627183196049774781754190", "FR8370771610771802086910638", "FR6728578752777372934914891"]),
    "C104512": ("FR8530004012343256446669362", ["FR4842935559529956576285257", "FR7878203960954265678384473", "FR7937749909028749221907685"]),
}
BIC_BANQUE = "AZURFRPPXXX"
BICS_BENEF = ["BNPAFRPPXXX", "SOGEFRPPXXX", "CRLYFRPPXXX", "AGRIFRPPXXX", "CMCIFRPPXXX", "PSSTFRPPXXX"]
MULE = ("LT214236743354831348", "REVOLT21XXX")   # compte de réception de la fraude, jamais vu pour ce client


def iban_fr_aleatoire():
    """IBAN français fictif mais valide (clé ISO 13616), pour les nouveaux bénéficiaires légitimes."""
    bban = f"{random.randint(10000, 99999)}{random.randint(10000, 99999)}{random.randint(10**10, 10**11 - 1)}{random.randint(10, 96):02d}"
    n = int("".join(str(int(c, 36)) for c in bban + "FR00"))
    return f"FR{98 - n % 97:02d}{bban}"


def ligne(ts, **kv):
    corps = " ".join(f"{k}={v}" for k, v in kv.items())
    return f"<134>1 {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} sepa-hub-01 SEPA - CT_OUT - {corps}\n"


def virement(ts, client, schema, creditor, bic, montant, canal):
    return ligne(ts, scheme=schema, e2e=f"AZB{ts:%y%m%d%H%M%S}{random.randint(1000, 9999)}", client=client,
                 debtor_iban=CLIENTS[client][0], debtor_bic=BIC_BANQUE, creditor_iban=creditor, creditor_bic=bic,
                 amount=f"{montant:.2f}", currency="EUR", channel=canal, status="ACCP")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=6, help="nombre de virements normaux")
    ap.add_argument("--fraude", action="store_true")
    ap.add_argument("--normal-unique", action="store_true")
    ap.add_argument("--date", help="horodatage UTC imposé, ex. 2026-11-13T22:00:00Z")
    a = ap.parse_args()
    ts = dt.datetime.fromisoformat(a.date.replace("Z", "+00:00")) if a.date else dt.datetime.now(dt.timezone.utc)
    msgs = []
    for _ in range(a.n):
        client = random.choice(list(CLIENTS))
        schema = random.choice(["SCT", "SCT", "SCT", "SCT_INST"])
        montant = random.uniform(20, 8000) if schema == "SCT" else random.uniform(10, 2500)
        if random.random() < 0.1:
            # Nouveau bénéficiaire légitime : petit montant, sous les seuils de la règle.
            creditor, montant = iban_fr_aleatoire(), random.uniform(15, 900)
        else:
            creditor = random.choice(CLIENTS[client][1])
        msgs.append(virement(ts, client, schema, creditor, random.choice(BICS_BENEF), montant,
                             random.choice(["banque_en_ligne"] * 4 + ["agence"])))
    if a.normal_unique:
        msgs.append(virement(ts, "C102310", "SCT", CLIENTS["C102310"][1][0], "BNPAFRPPXXX", 1250.00, "banque_en_ligne"))
    if a.fraude:
        # Prise de contrôle du compte en ligne : virement instantané (irrévocable en 10 s) vers un compte mule.
        msgs.append(virement(ts, "C104512", "SCT_INST", MULE[0], MULE[1], 48000.00, "banque_en_ligne"))
    with socket.create_connection(DEST, timeout=10) as s:
        s.sendall("".join(msgs).encode())
    print(f"{len(msgs)} virement(s) envoyé(s) à {DEST[0]}:{DEST[1]}")


if __name__ == "__main__":
    main()
