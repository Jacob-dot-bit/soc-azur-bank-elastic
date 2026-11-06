# Captures : collecte (partie A)

Prises le 6 novembre 2026 sur le SIEM on-prem (Kibana 9.5.6, siem-elk-01).

| Fichier | Ce qu'elle montre |
| --- | --- |
| `fleet-agents.png` | Fleet > Agents : les 5 agents du lab (ws-agence, srv-dc01, bastion-01, web-portail-01, db-clients-01) et le Fleet Server (siem-elk-01) en état *Sain*, version 9.5.6, chacun avec sa politique |
| `discover-logs-agents.png` | Discover sur `logs-*`, dernière heure, `host.name : * and not host.name : "siem-elk-01"`, réparti par `host.name` : les journaux des 5 machines arrivent en continu (2 116 documents en une heure) |
