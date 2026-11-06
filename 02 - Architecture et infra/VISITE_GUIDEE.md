# Visite guidée du lab SOC Azur Bank

Mis à jour le 6 novembre 2026.

## Avant de commencer

Un log fait toujours le même trajet : une machine écrit un journal, l'Elastic Agent le lit et l'envoie au SIEM on-prem siem-elk-01 (zone SOC), un ingest pipeline le range en champs ECS, une règle le surveille, et une alerte devient un case puis une action SOAR. Ce guide suit ce trajet maillon par maillon. Pour chaque maillon : ce qu'il fait, comment le vérifier, et les commandes pour le refaire.

```
Machine → Elastic Agent → Ingest pipeline → Data stream
                                                 ↓
Workflow SOAR ← Case ← Alerte ←───────────── Règle
```

Les maillons 1 à 6 couvrent la rangée du haut et la règle. Le maillon 7 couvre le case et le workflow, qui restent à construire.

Tout se passe depuis le Proxmox (`ssh root@100.106.21.10`, la clé SSH chargée avec `ssh-add`). Les conteneurs se pilotent avec `pct exec <id> -- <commande>`, les VM Windows par la console Proxmox ou RDP, et fw-01 par sa console série.

| ID | Machine | Zone | IP |
| --- | --- | --- | --- |
| 200 | fw-01 (OPNsense) | toutes | 192.168.100.2 (WAN), .1 dans chaque zone |
| 201 | srv-dc01 (AD) | DC | 10.10.1.10 |
| 202 | ws-agence (Windows 11) | LAN | 10.20.30.47 |
| 210 | db-clients-01 (PostgreSQL) | DC | 10.10.1.20 |
| 211 | web-portail-01 (nginx) | DMZ | 10.30.0.10 |
| 212 | bastion-01 (SSH) | ADM | 10.0.5.10 |

Pour les appels à l'API Elastic, la clé reste dans une variable : `export ES_API_KEY=...`, puis on-prem (sur siem-elk-01, `ssh -J root@100.106.21.10 jakub@10.40.0.10`) `ES=https://10.40.0.10:9200` et `KB=https://10.40.0.10:5601`, avec `--cacert` (voir `02 - Architecture et infra/INFRA.md`, section SIEM on-prem). Partie Cloud (données de démo, essai jusqu'au 19/11) : `ES=https://<projet>.es.<region>.gcp.elastic.cloud` et `KB=https://<projet>.kb.<region>.gcp.elastic.cloud`. Les mots de passe du lab sont dans `Accès lab (confidentiel, ne pas partager)/mots-de-passe-lab.xlsx`.

## 1. Réseau et pare-feu fw-01

**Ce qu'il fait.** Quatre bridges Proxmox sans IP (`vmbr2` LAN, `vmbr3` DC, `vmbr4` DMZ, `vmbr5` ADM) isolent les zones. L'hôte ne route pas entre eux : seul fw-01 a une patte dans chaque zone. Son WAN est sur `vmbr1`, et l'hôte fait le NAT vers Internet. Les règles appliquent la logique bancaire : le LAN n'atteint pas la base, seule la zone ADM y accède, et les zones ne sortent qu'en 80/443. Chaque décision est journalisée et envoyée en syslog au bastion.

**Le vérifier.**

- Les bridges : `ip -br link | grep vmbr` sur le Proxmox.
- Le filtrage, vu depuis deux zones : `pct exec 212 -- ping -c1 10.10.1.20` répond (ADM), `pct exec 211 -- ping -c1 -W2 10.10.1.20` échoue (DMZ).
- Les règles dans l'interface : depuis ws-agence (console Proxmox ou RDP), ouvrir `https://10.20.30.1` (autorisé par la règle anti-verrouillage du LAN), puis Firewall > Rules, un onglet par zone.
- Les journaux dans Kibana : Discover, data view `logs-pfsense.log-*`, filtrer `event.action : block`.

**Le refaire.**

1. Créer un bridge : `pvesh create /nodes/$(hostname)/network --iface vmbr6 --type bridge --autostart 1`, puis `pvesh set /nodes/$(hostname)/network` pour appliquer.
2. Se connecter à la console de fw-01 : `qm terminal 200` (sortie avec Ctrl+O), compte `root`. L'option 8 ouvre un shell, et `pfctl -sr` liste les règles actives.
3. Ajouter une règle dans l'interface web, par exemple bloquer DMZ → Internet en 80, puis vérifier dans Kibana que `curl` depuis web-portail-01 produit un `block`.
4. La configuration complète est générée par `infra/fw_config.py` : le lire pour voir comment une règle s'écrit dans `config.xml`.

## 2. Fleet (on-prem) et Elastic Cloud

**Ce qu'il fait.** Fleet est la console qui pilote les agents. Une politique d'agent regroupe des intégrations, et chaque intégration décrit ce qu'il faut lire et où l'écrire. Chaque agent appelle Fleet Server en HTTPS (siem-elk-01, port 8220), reçoit sa politique et envoie ses données à Elasticsearch (port 9200) dans des data streams nommés `logs-<dataset>-<namespace>`. Les flux restent dans le lab et passent par fw-01, qui n'autorise que ces deux ports vers la zone SOC. Le tout tourne en licence Basic, gratuite. Le projet Elastic Cloud montre la partie Cloud de l'hybride, avec les données de démo `logs-*-banque`.

| Politique | Machines | Intégrations | Data streams principaux |
| --- | --- | --- | --- |
| pol-linux-db | db-clients-01 | System, Custom Logs (pgaudit) | `logs-db.audit-default`, `logs-system.auth-default` |
| pol-linux-web | web-portail-01 | System, Nginx | `logs-nginx.access-default` |
| pol-linux-bastion | bastion-01 | System, pfSense/OPNsense (UDP 514) | `logs-pfsense.log-default`, `logs-system.auth-default` |
| pol-windows | srv-dc01, ws-agence | System, Windows, Elastic Defend | `logs-system.security-default`, `logs-windows.sysmon_operational-default`, `logs-endpoint.events.*` |

**Le vérifier.**

- Kibana > Fleet > Agents : les 5 agents du lab (plus siem-elk-01, qui porte Fleet Server) doivent être *Healthy*. Un clic sur un agent montre sa politique et ses journaux.
- Kibana > Stack Management > Index Management > Data Streams : le nombre de documents par data stream.
- Sur une machine Linux : `pct exec 210 -- elastic-agent status`.
- Par l'API : `curl -s -H "Authorization: ApiKey $ES_API_KEY" "$KB/api/fleet/agents"`.

**Le refaire.**

1. Fleet > Agent policies > Create agent policy, puis Add integration (par exemple System).
2. Add agent : Kibana affiche la commande d'installation avec l'URL Fleet et le jeton d'enrôlement. La copier telle quelle sur la machine.
3. Pour désinstaller puis réinstaller un agent Linux : `elastic-agent uninstall`, puis la commande de Kibana.
4. Le script `infra/creer_politiques.py` crée les 4 politiques par l'API. Le lire pour voir le format attendu par Fleet.

## 3. Base clients, pgaudit et alerte d'exfiltration

**Ce qu'il fait.** C'est le cœur du use case. pgaudit écrit une ligne par lecture ou écriture sur une table, dans `/var/log/postgresql/postgresql-17-main.log`. L'agent lit ce fichier (dataset `db.audit`) et l'envoie brut. L'ingest pipeline `db-audit-pgaudit` découpe alors la ligne en champs ECS. La règle Threshold compte ensuite les `select` sur `clients` par utilisateur.

Une ligne brute :

```
2026-11-05 15:42:33.301 UTC [3211] c_dupont@core_clients 10.0.5.10 LOG:  AUDIT: SESSION,600,1,READ,SELECT,TABLE,public.clients,SELECT * FROM clients WHERE id=600,<not logged>
```

| Morceau de la ligne | Champ produit par le pipeline |
| --- | --- |
| `c_dupont` | `user.name` |
| `core_clients` | `db.name` |
| `10.0.5.10` | `source.ip` |
| `SELECT` (ou `COPY ... TO`) | `event.action` : `select` (ou `export`) |
| `public.clients` | `object` : `clients`, `db.table` |
| la requête | `db.statement` |

**Le vérifier.**

- La config pgaudit : `pct exec 210 -- su postgres -c "psql -c 'SHOW pgaudit.log;'"` doit répondre `read,write`.
- Les lignes brutes : `pct exec 210 -- tail -f /var/log/postgresql/postgresql-17-main.log`.
- Le pipeline : Stack Management > Ingest Pipelines > `db-audit-pgaudit`, bouton *Test pipeline* avec la ligne ci-dessus.
- Les documents : Discover, `logs-db.audit-default`, requête KQL `event.action : "select" and object : "clients"`.
- L'alerte : Security > Alerts, règle « Lecture massive base clients ».

**Le refaire (rejouer l'exfiltration).** Depuis le bastion, 600 lectures puis un export avec le compte `c_dupont` :

```
pct exec 212 -- bash -c 'export PGPASSWORD="<mot de passe c_dupont>"
for i in $(seq 1 600); do echo "SELECT * FROM clients WHERE id=$i;"; done | psql -q -h 10.10.1.20 -U c_dupont -d core_clients > /dev/null
psql -q -h 10.10.1.20 -U c_dupont -d core_clients -c "COPY clients TO STDOUT" > /dev/null'
```

Compter une à deux minutes avant l'alerte : la collecte prend quelques secondes, et la règle tourne chaque minute. Pour comprendre le pipeline, modifier un processeur dans `infra/pipeline_db_audit_pgaudit.json`, le tester avec *Test pipeline*, puis l'envoyer : `curl -XPUT -H "Authorization: ApiKey $ES_API_KEY" -H 'Content-Type: application/json' "$ES/_ingest/pipeline/db-audit-pgaudit" -d @infra/pipeline_db_audit_pgaudit.json`.

## 4. Portail web nginx

**Ce qu'il fait.** web-portail-01 sert le portail client en DMZ. La page `/compte?id=` simule une consultation de compte. Chaque requête est écrite dans `/var/log/nginx/access.log`. L'intégration Nginx la découpe (`source.ip`, `url.original`, `http.response.status_code`, `user_agent`) dans `logs-nginx.access-default`.

**Le vérifier.**

- Le site répond : `pct exec 212 -- curl -s "http://10.30.0.10/compte?id=1"`.
- Le journal brut : `pct exec 211 -- tail -f /var/log/nginx/access.log`.
- Discover, `logs-nginx.access-*`, filtrer `url.original : *compte*`.

**Le refaire (une injection SQL).** Lancer une requête piégée depuis le bastion ou ws-agence :

```
pct exec 212 -- curl -s "http://10.30.0.10/compte?id=1'%20OR%20'1'='1"
```

Elle doit apparaître dans Discover quelques secondes plus tard. Écrire ensuite soi-même une requête KQL qui la retrouve, par exemple `url.original : *OR*`, puis en faire une règle de détection *Custom query*. C'est le meilleur exercice pour comprendre le passage d'une recherche à une règle.

## 5. Bastion SSH

**Ce qu'il fait.** bastion-01 est le seul point d'entrée d'administration vers la zone DC. Il a deux rôles. D'abord, il accepte SSH par clé, ou par mot de passe suivi d'un code TOTP. Ensuite, son agent écoute en UDP 514 les journaux de fw-01. Les connexions sont écrites dans `/var/log/auth.log` (par rsyslog) et arrivent dans `logs-system.auth-default`.

Le module TOTP est en mode `nullok` : un compte qui n'a pas encore enrôlé de TOTP se connecte sans MFA. C'est volontaire, car cela reproduit le scénario de la démo (connexion d'adm.fontaine sans MFA après une force brute).

**Le vérifier.**

- La config SSH : `pct exec 212 -- cat /etc/ssh/sshd_config.d/10-bastion.conf` et `pct exec 212 -- head -1 /etc/pam.d/sshd`.
- L'écoute syslog : `pct exec 212 -- ss -lunp | grep 514`.
- Discover, `logs-system.auth-*`, filtrer `event.outcome : failure`.

**Le refaire.**

1. Enrôler le TOTP d'un compte : `pct exec 212 -- su - adm.fontaine -c google-authenticator`, puis scanner le QR code avec une application d'authentification. À partir de là, ce compte doit donner son code.
2. Simuler une force brute : installer `sshpass` (`pct exec 212 -- apt install -y sshpass`), puis `pct exec 212 -- bash -c 'for i in $(seq 1 20); do sshpass -p faux ssh -o StrictHostKeyChecking=no adm.fontaine@127.0.0.1 true; done'`.
3. Retrouver les 20 échecs dans Kibana, puis écrire une règle Threshold (par exemple 10 échecs en 5 minutes par `source.ip` et `user.name`).

## 6. Annuaire et postes Windows

**Ce qu'il fait.** srv-dc01 porte le domaine `azurbank.local` et sert de DNS aux machines Windows. ws-agence est le poste du guichetier, joint au domaine dans l'OU Agences. Sur les deux, trois sources se complètent :

- le journal Security (ouvertures de session 4624/4625, création de comptes, Kerberos), activé par `auditpol` ;
- Sysmon (config SwiftOnSecurity), qui trace les processus, le réseau et les fichiers avec plus de détail ;
- Elastic Defend, l'EDR d'Elastic, qui envoie ses propres événements (`logs-endpoint.events.*`) et peut bloquer un comportement malveillant.

Les deux Windows sont des versions d'évaluation. ws-agence expire le 4 février 2027 et srv-dc01 le 4 mai 2027. Si un poste s'éteint tout seul toutes les heures, c'est le signe d'une évaluation expirée : `slmgr /xpr` le confirme, et `slmgr /rearm` puis un redémarrage la prolonge.

**Le vérifier.**

- Sur un Windows, en PowerShell : `Get-Service Sysmon64, "Elastic Agent"` et `auditpol /get /category:*`.
- L'annuaire, sur srv-dc01 : `Get-ADUser -Filter * | Select SamAccountName` et `Get-ADComputer -Filter *`.
- Kibana > Security > Hosts : les deux machines avec leurs événements.
- Discover : `host.name : "ws-agence" and event.code : 4625` pour les échecs d'ouverture de session.

**Le refaire.**

1. Sur ws-agence, se tromper trois fois de mot de passe sur `c.dupont`, puis retrouver les trois événements 4625 dans Kibana.
2. Lancer `whoami /all` et `net group "Admins du domaine" /domain`, deux commandes typiques de reconnaissance. Les retrouver dans Sysmon (event 1) et dans `logs-endpoint.events.process`, puis regarder si une règle préconstruite d'Elastic les signale.
3. Créer un utilisateur dans l'AD (`New-ADUser`) et retrouver l'événement 4720 : c'est la base d'une règle « création de compte hors processus ».

## 7. Réponse et SOAR (Shuffle)

**Ce qu'il fait.** Les alertes sont triées dans Kibana (Alerts, puis Cases). La réponse automatique est confiée à Shuffle, un SOAR open source, sur soar-shuffle-01 (10.40.0.20, zone SOC). En licence Basic, Kibana ne peut pas appeler de webhook, ni isoler un poste ou lancer un Workflow : c'est donc Shuffle qui interroge l'API toutes les minutes. Le playbook « Azur Bank - Réponse exfiltration et fraude SWIFT » enchaîne quatre étapes :

1. lire les alertes ouvertes du use case (et de la règle SWIFT) ;
2. ouvrir un case Kibana par compte et y attacher les alertes ;
3. confiner : rôle PostgreSQL en `NOLOGIN` et sessions coupées sur db-clients-01, compte AD désactivé sur srv-dc01, IP source bloquée sur fw-01 si elle vient d'Internet ;
4. écrire le bilan dans le case, passer les alertes en *Acknowledged* avec l'étiquette `soar-traite`.

Chaque action passe par un compte de service aux droits minimaux : `svc-shuffle` sur la base (sudo sur un seul script), `svc.shuffle` dans l'AD (Opérateurs de compte, SSH réservé à 10.40.0.20), `svc-shuffle` sur fw-01 (API limitée aux tables d'alias) et `svc-shuffle` dans Elastic (alertes et cases).

**Le vérifier.**

- Rejouer l'exfiltration (maillon 3). Dans la minute qui suit, `psql` en c_dupont répond `role "c_dupont" is not permitted to log in`, et c.dupont est désactivé dans l'AD.
- Kibana > Cases : le case « [SOAR] Exfiltration base clients - compte c_dupont » contient les alertes et le bilan des actions.
- Shuffle (tunnel `ssh -L 3443:10.40.0.20:3443 root@100.106.21.10`, puis https://localhost:3443) > Workflows > Runs : le détail de chaque nœud.
- Remettre le compte en état après la démo, depuis l'hôte : `bash /root/soc-enroll/reinitialiser_demo.sh`.

**Le refaire / le faire évoluer.** Le code des nœuds est dans `04 - Réponse à incident et SOAR/soar-shuffle-01/playbook/`, et `creer_workflow.py` recrée le workflow. La variable `actions_actives` du workflow (`oui`/`non`) bascule entre confinement réel et simulation. À faire en groupe : rédiger les 5W dans le case, ajouter une branche pour la force brute du bastion (IP externe, donc bloquée sur fw-01), et mesurer le temps entre l'export et le confinement (MTTR).

## Pour s'approprier le lab

Le plus formateur est de casser un maillon puis de le réparer : on comprend à quoi il sert quand l'alerte ne vient plus. Chaque exercice suit la répartition des rôles du groupe.

| Rôle | Exercice | Ce qu'on doit observer |
| --- | --- | --- |
| Infra / ingestion (A, B) | Retirer le processeur `script` du pipeline pgaudit, rejouer l'exfiltration | Les documents arrivent sans `event.action` ni `object`, et la règle ne se déclenche plus |
| Infra / ingestion (A, B) | Bloquer le flux 8220/9200 de la zone DC vers siem-elk-01 sur fw-01 | db-clients-01 passe *Offline* dans Fleet, et le bloc apparaît dans `logs-pfsense.log-*` |
| Détection (C) | Abaisser le seuil de la règle à 50, rejouer 100 lectures | L'alerte se lève. On discute alors du réglage seuil contre faux positifs |
| Détection (C) | Écrire la règle SQLi (maillon 4) et la règle force brute (maillon 5) | Chaque test lève exactement une alerte |
| SOAR / incident (D, G) | Passer `actions_actives` à `non`, rejouer l'exfiltration, puis à `oui` | En simulation, le case se crée sans confinement ; en réel, c_dupont est bloqué en moins de 2 min |
| Dashboard / soutenance (E, F) | Construire un Lens « alertes par règle et par jour » sur les données réelles du lab | Le pic de l'exfiltration rejouée apparaît sur le graphique |

Un conseil : rejouer d'abord chaque test tel quel, pour voir le résultat attendu, avant de modifier quoi que ce soit.
