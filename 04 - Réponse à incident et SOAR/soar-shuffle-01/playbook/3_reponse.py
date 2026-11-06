# Noeud 3 : actions de confinement. Activées seulement si actions_actives vaut « oui ».
#  - exfiltration : rôle PostgreSQL en NOLOGIN + sessions coupées (SSH svc-shuffle -> db-clients-01),
#                   compte AD désactivé (SSH svc.shuffle -> srv-dc01), IP source bloquée si elle est externe
#  - swift        : compte AD de l'opérateur désactivé
import io, ipaddress, json, re, requests, paramiko
data = json.loads(r'''$ouvrir_case.message''')
ACTIF = "$actions_actives".strip().lower() == "oui"

def ssh(host, user, cmd, key=None, password=None):
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pk = paramiko.Ed25519Key.from_private_key(io.StringIO(key)) if key else None
    c.connect(host, username=user, pkey=pk, password=password, timeout=15, look_for_keys=False, allow_agent=False)
    _, out, err = c.exec_command(cmd, timeout=60)
    res = (out.read() + err.read()).decode(errors="replace").strip(); c.close(); return res

def compte_ad(user):
    # Convention Azur Bank : rôle base c_dupont <-> compte AD c.dupont
    return user.replace("_", ".")

for i in data["incidents"]:
    actions = []
    u = i["user"]
    if not ACTIF:
        actions.append("Mode simulation (actions_actives != oui) : aucune action de confinement exécutée.")
    else:
        if i["type"] == "exfiltration" and re.fullmatch(r"[a-z][a-z0-9_]{1,30}", u):
            try:
                actions.append("Base : " + ssh("10.10.1.20", "svc-shuffle", f"sudo /usr/local/sbin/soar-verrou-db.sh {u}",
                                               key="""$ssh_key_soar"""))
            except Exception as e:
                actions.append(f"Base : échec ({e})")
        ad = compte_ad(u)
        if re.fullmatch(r"[a-z][a-z0-9.]{1,30}", ad):
            try:
                out = ssh("10.10.1.10", "svc.shuffle@azurbank.local",
                          f"powershell -NoProfile -Command \"Disable-ADAccount -Identity {ad}; "
                          f"(Get-ADUser {ad}).Enabled\"", password="""$ad_password""")
                actions.append(f"AD : compte {ad} désactivé (Enabled = {out.splitlines()[-1] if out else '?'})")
            except Exception as e:
                actions.append(f"AD : échec ({e})")
        for ip in i["source_ip"]:
            if ipaddress.ip_address(ip).is_private:
                actions.append(f"Pare-feu : {ip} est une IP interne, pas de blocage (compte déjà confiné)")
                continue
            try:
                r = requests.post(f"https://10.40.0.1/api/firewall/alias_util/add/BLOCKLIST_SOAR", json={"address": ip},
                                  auth=("$opn_key", "$opn_secret"), verify=False, timeout=15)
                actions.append(f"Pare-feu : {ip} ajoutée à BLOCKLIST_SOAR ({r.json().get('status')})")
            except Exception as e:
                actions.append(f"Pare-feu : échec ({e})")
    i["actions"] = actions
print(json.dumps(data))
