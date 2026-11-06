# Partie B : normalisation ECS et requêtes de recherche

Toutes les sources du lab arrivent dans Elasticsearch au format **ECS** (Elastic Common Schema). Un même champ a le même nom,
quelle que soit la source : `user.name` désigne aussi bien le compte AD d'une ouverture de session Windows que le rôle PostgreSQL
d'une requête sur la base. C'est ce qui permet d'écrire une règle ou une requête qui croise plusieurs sources.

Toutes les requêtes ci-dessous ont été lancées le 6 novembre 2026 sur le SIEM on-prem (siem-elk-01). Le nombre de résultats
obtenu figure en fin de ligne. Les requêtes KQL se tapent dans Kibana > Discover ou dans Security > Timelines, et les requêtes
EQL dans Security > Timelines > onglet *Correlation*.

## 1. Mapping ECS des sources

| Source (machine) | Collecte | Data stream | Champs ECS utilisés | Champs propres à la source |
| --- | --- | --- | --- | --- |
| Base clients PostgreSQL + pgaudit (db-clients-01) | Elastic Agent, *Custom Logs (filestream)* + ingest pipeline `db-audit-pgaudit` | `logs-db.audit-default` | `event.action` (`select`, `insert`, `update`, `delete`, `export`), `user.name` (rôle PostgreSQL), `source.ip`, `host.name`, `db.statement` | `object` (table visée, champ hors ECS gardé pour lisibilité ; `db.table` serait plus propre) |
| Portail web nginx (web-portail-01) | Intégration *Nginx* | `logs-nginx.access-default` | `source.ip`, `url.original`, `url.path`, `url.query`, `http.request.method`, `http.response.status_code`, `user_agent.original`, `event.outcome` | - |
| Bastion SSH (bastion-01) | Intégration *System* (journal auth / journald) | `logs-system.auth-default` | `event.category` (`authentication`, `session`), `event.outcome`, `user.name`, `source.ip`, `process.name` (`sshd`) | - |
| Pare-feu OPNsense (fw-01) | Syslog UDP 514 vers le bastion, intégration *pfSense* | `logs-pfsense.log-default` | `event.action` (`pass`, `block`), `source.ip`/`.port`, `destination.ip`/`.port`, `network.transport`, `network.direction`, `observer.ingress.interface.name`, `rule.id` | - |
| Active Directory et postes Windows (srv-dc01, ws-agence) | Intégration *System* (journal Security) | `logs-system.security-default` | `event.code` (ID Windows : 4624, 4625, 4720, 4728...), `event.action`, `event.outcome`, `user.name`, `user.domain`, `host.name` | `winlog.event_data.*` (ex. `TargetUserName`, `LogonType`), `winlog.logon.type` |
| Sysmon (srv-dc01, ws-agence) | Intégration *Windows* | `logs-windows.sysmon_operational-default` | `event.code` (1 = création de processus, 3 = connexion réseau...), `process.name`, `process.command_line`, `process.parent.name`, `process.hash.sha256`, `user.name` | `winlog.*` |
| PowerShell (srv-dc01, ws-agence) | Intégration *Windows* | `logs-windows.powershell*-default` | `event.code` (4104 = bloc de script), `process.*`, `user.name` | `powershell.file.script_block_text` |
| Passerelle SWIFT (simulée, bastion-01) | Syslog TCP 5514 vers **Logstash** (grok + kv + translate + ruby) | `logs-swift.gateway-default` | `event.action` (`MSG_OUT`, `MSG_IN`), `event.outcome`, `user.name` (opérateur), `host.name`, `observer.vendor`/`.product` | `swift.message_type`, `swift.amount`, `swift.currency`, `swift.receiver`, `swift.ref`, `swift.correspondant_connu`, `swift.hors_heures_ouvrees` |
| Alertes du SIEM | Moteur de détection Kibana | `.alerts-security.alerts-default` | `kibana.alert.rule.name`, `kibana.alert.severity`, `kibana.alert.workflow_status`, + les champs ECS de l'événement d'origine | `kibana.alert.*` |

Ce qu'apporte la normalisation, avec deux exemples du lab :

- **pgaudit.** PostgreSQL écrit une ligne brute (`AUDIT: SESSION,1,1,READ,SELECT,TABLE,public.clients,...`).
  L'ingest pipeline la découpe (dissect), puis en tire `event.action: select`, `object: clients` et `user.name: c_dupont`.
  Sans ces champs, la règle d'exfiltration ne voit rien.
- **SWIFT.** Logstash range la ligne syslog de la passerelle dans les mêmes champs (`user.name`, `event.action`). Il y ajoute
  aussi deux champs métier : le correspondant est-il au référentiel, et le virement part-il hors heures ouvrées ? La règle
  n'a plus qu'à les tester.

## 2. Requêtes KQL commentées

KQL (*Kibana Query Language*) filtre des événements un par un : c'est l'outil de la recherche et du triage.

```kql
// K1. Toutes les lectures de la table clients par un compte donné (triage de l'alerte d'exfiltration)
event.dataset : "db.audit" and event.action : "select" and object : "clients" and user.name : "c_dupont"
```
→ 3 002 lectures sur la journée, dont les rafales de 600 des tests.

```kql
// K2. Exports de données (COPY ... TO) : rares en temps normal, donc à regarder un par un
event.dataset : "db.audit" and event.action : "export"
```
→ 5 exports, tous issus des tests d'exfiltration.

```kql
// K3. Requêtes du portail portant une charge d'injection SQL ou l'empreinte de sqlmap
event.dataset : "nginx.access" and (user_agent.original : *sqlmap* or url.original : (*UNION* or *%27*))
```
→ 19 requêtes depuis 10.0.5.10 (test du 6 novembre). Variante utile : ajouter `and http.response.status_code : 200`
pour ne garder que les injections que le serveur a acceptées.

```kql
// K4. Échecs d'authentification SSH sur le bastion
event.dataset : "system.auth" and event.category : "authentication" and event.outcome : "failure" and host.name : "bastion-01"
```
→ 15 échecs sur `adm.fontaine` (test de force brute).

```kql
// K5. Échecs d'ouverture de session Windows (événement 4625), sur le DC et les postes
event.dataset : "system.security" and event.code : "4625"
```
→ 2. À croiser avec `winlog.logon.type` : 3 pour le réseau, 10 pour RDP.

```kql
// K6. Ajout d'un membre à un groupe de sécurité global, local ou universel (4728, 4732, 4756)
event.dataset : "system.security" and event.code : ("4728" or "4732" or "4756")
```
→ 33, liés à la mise en place du lab (notamment le compte de service du SOAR, ajouté à deux groupes le 6 novembre). En production, tout ajout à
« Admins du domaine » doit être justifié par un ticket.

```kql
// K7. PowerShell lancé avec une commande encodée en Base64, technique classique pour masquer une charge (Sysmon, ID 1)
event.dataset : "windows.sysmon_operational" and event.code : "1" and process.name : "powershell.exe"
  and process.command_line : (*-enc* or *-EncodedCommand*)
```
→ 1 (test sur ws-agence avec `-EncodedCommand`).

```kql
// K8. Flux bloqués par fw-01 vers la base clients : une tentative depuis le LAN est anormale (seul ADM y a accès)
event.dataset : "pfsense.log" and event.action : "block" and destination.ip : "10.10.1.20"
```
→ 6 (test `Test-NetConnection 10.10.1.20 -Port 5432` depuis ws-agence).

```kql
// K9. Virements SWIFT hors norme : 1 M EUR ou plus, ou correspondant hors référentiel
event.dataset : "swift.gateway" and (swift.amount >= 1000000 or swift.correspondant_connu : false)
```
→ 3 (les MT103 de test du simulateur).

## 3. Requêtes EQL commentées

EQL (*Event Query Language*) relie plusieurs événements entre eux. Une *sequence* décrit un enchaînement dans le temps
(A puis B, sur la même clé) que KQL ne sait pas exprimer.

```eql
// E1. Collecte puis exfiltration : 100 lectures de la table clients puis un export, par le même compte, en 10 min
sequence by user.name with maxspan=10m
  [any where event.dataset == "db.audit" and event.action == "select" and object == "clients"] with runs=100
  [any where event.dataset == "db.audit" and event.action == "export"]
```
→ 3 séquences, une par test. C'est la règle « Lecture massive base clients puis export ».

```eql
// E2. Force brute réussie : 10 échecs puis un succès, même IP et même compte, en 10 min
sequence by source.ip, user.name with maxspan=10m
  [authentication where event.outcome == "failure"] with runs=10
  [authentication where event.outcome == "success"]
```
→ 1 séquence (`adm.fontaine`). `authentication where` est un raccourci EQL pour `event.category == "authentication"`.

```eql
// E3. Une application bureautique qui lance un interpréteur de commandes : macro malveillante (T1204, T1059)
process where event.code == "1"
  and process.parent.name : ("winword.exe", "excel.exe", "outlook.exe")
  and process.name : ("powershell.exe", "cmd.exe", "wscript.exe", "mshta.exe")
```
→ 0 sur le lab (aucune macro lancée). L'opérateur `:` compare sans tenir compte de la casse.

```eql
// E4. Force brute sur un compte Windows : 5 échecs (4625) puis une ouverture réussie (4624) en 5 min
sequence by user.name with maxspan=5m
  [authentication where event.code == "4625"] with runs=5
  [authentication where event.code == "4624"]
```
→ 0. Même logique que E2, appliquée à l'AD.

```eql
// E5. certutil détourné pour télécharger un fichier (LOLBin, T1105)
process where process.name : "certutil.exe" and process.args : ("-urlcache", "/urlcache", "-split", "-f")
```
→ 0.

```eql
// E6. Persistance : création d'un compte (4720) puis son ajout à un groupe (4728, 4732, 4756) dans l'heure
sequence by winlog.event_data.TargetSid with maxspan=1h
  [iam where event.code == "4720"]
  [iam where event.code in ("4728", "4732", "4756")]
```
→ 0 dans la fenêtre testée.

Les requêtes à 0 résultat ont la bonne syntaxe (l'API EQL les accepte) mais n'ont pas trouvé l'attaque, qui n'a pas été
rejouée. Ce sont de bons exercices de chasse : lancer la technique sur ws-agence, puis vérifier que la requête la trouve.

## 4. Refaire les tests

Les requêtes se rejouent depuis Kibana ou par l'API (sur siem-elk-01) :

```bash
# KQL n'existe que dans Kibana ; par l'API, l'équivalent est une requête query_string (syntaxe Lucene)
curl -s --cacert /root/elastic/http_ca.crt -H "Authorization: ApiKey $ES_API_KEY" -H 'Content-Type: application/json' \
  "https://10.40.0.10:9200/logs-db.audit-*/_count" \
  -d '{"query":{"query_string":{"query":"event.action:\"export\""}}}'

# EQL
curl -s --cacert /root/elastic/http_ca.crt -H "Authorization: ApiKey $ES_API_KEY" -H 'Content-Type: application/json' \
  "https://10.40.0.10:9200/logs-system.auth-*/_eql/search" \
  -d '{"query":"sequence by source.ip, user.name with maxspan=10m [authentication where event.outcome == \"failure\"] with runs=10 [authentication where event.outcome == \"success\"]"}'
```
