# Infra de base — Azur Bank SOC (Elastic Security)

## Vue d'ensemble (hybride)

```
            CLOUD (Elastic Cloud Serverless, GCP us-east4 : essai du lab ; cible de production : Elastic Cloud Hosted)
   ┌──────────────────────────────────────────────────────────┐
   │ Elastic Security : partie Cloud de l'hybride (démo,      │
   │ essai jusqu'au 19/11) : données logs-*-banque, Workflows │
   └───────────────▲──────────────────────────────────────────┘
                   │ HTTPS 443 sortant uniquement (TLS)
   ┌───────────────┴──────────────────────────────────────────┐
   │ ON-PREM (Proxmox)                                        │
   │                                                          │
   │  vmbr6 "SOC"  10.40.0.0/24   ── siem-elk-01              │
   │     Elasticsearch + Kibana + Fleet Server, licence Basic │
   │     (gratuite, sans date de fin) : reçoit tous les agents│
   │  vmbr2 "LAN"  10.20.30.0/24  ── ws-agence (Windows 11)   │
   │  vmbr3 "DC"   10.10.1.0/24   ── srv-dc01 (AD, Windows)   │
   │                              ── db-clients-01 (Postgres) │
   │  vmbr4 "DMZ"  10.30.0.0/24   ── web-portail-01 (nginx)   │
   │  vmbr5 "ADM"  10.0.5.0/24    ── bastion-01 (Linux SSH)   │
   │                                                          │
   │  fw-01 (OPNsense/pfSense) route + filtre entre zones,    │
   │  seule sortie Internet → logs firewall vers le SIEM      │
   └──────────────────────────────────────────────────────────┘
```

Depuis le 6 novembre, chaque machine a un **Elastic Agent** enrôlé dans le **Fleet on-prem** de siem-elk-01
(8220 pour Fleet Server, 9200 pour Elasticsearch), à travers fw-01. Le SIEM fonctionne donc sans le cloud,
en licence Basic gratuite. Le projet Elastic Cloud reste la partie Cloud de l'architecture hybride (démo avec
les données `logs-*-banque`) tant que l'essai court (jusqu'au 19 novembre 2026).

## Infra déployée (5 novembre 2026)

| ID Proxmox | Nom | Type | Zone / bridge | IP | Politique Fleet |
|---|---|---|---|---|---|
| 200 | fw-01 | VM OPNsense 26.7 (2 vCPU / 2 Go) | WAN vmbr1 + 4 zones | 192.168.100.2 (WAN), 10.20.30.1, 10.10.1.1, 10.30.0.1, 10.0.5.1 | (syslog → bastion) |
| 201 | srv-dc01 | VM Windows Server 2025 (clone du template 9000) | DC / vmbr3 | 10.10.1.10 | pol-windows |
| 202 | ws-agence | VM Windows 11 Entreprise eval 24H2 (2 vCPU / 4 Go, TPM, Secure Boot) | LAN / vmbr2 | 10.20.30.47 | pol-windows |
| 210 | db-clients-01 | LXC Debian 13 (2 vCPU / 2 Go) | DC / vmbr3 | 10.10.1.20 | pol-linux-db |
| 211 | web-portail-01 | LXC Debian 13 (1 vCPU / 1 Go) | DMZ / vmbr4 | 10.30.0.10 | pol-linux-web |
| 212 | bastion-01 | LXC Debian 13 (1 vCPU / 1 Go) | ADM / vmbr5 | 10.0.5.10 | pol-linux-bastion |
| 220 | siem-elk-01 | VM Debian 13 cloud-init (4 vCPU / 10 Go / 80 Go) | SOC / vmbr6 | 10.40.0.10 | fleet-server-policy |
| 221 | soar-shuffle-01 | VM Debian 13 cloud-init (2 vCPU / 6 Go / 40 Go), Docker | SOC / vmbr6 | 10.40.0.20 | (pas d'agent) |

Sur le Proxmox, toutes ces machines sont dans le pool `SOC-run` et portent l'étiquette `socrun`, avec une étiquette de zone
(`zone-lan`, `zone-dc`...) et une de rôle (`siem`, `soar`, `bastion`...).

ws-agence est joint au domaine (OU Agences) ; c.dupont et m.bernard peuvent s'y connecter, y compris en RDP.
Installation sans intervention : fichier de réponse dans `infra/ws-agence/`.

**Réseau.** `vmbr0` (IP publique OVH) et `vmbr1` (192.168.100.0/24, NAT de l'hôte, où se trouve aussi une VM hors projet, 106)
sont inchangés. Les zones utilisent donc `vmbr2` à `vmbr6`, des bridges sans IP sur l'hôte : seul fw-01 les relie.
Le WAN de fw-01 est sur `vmbr1`, la sortie Internet passe par le NAT de l'hôte (une seule IP publique).

**Filtrage fw-01** (règles journalisées, refus par défaut) : chaque zone → DNS et NTP de fw-01 ;
LAN → AD (srv-dc01) et portail DMZ (80/443) ; **LAN → base clients bloqué** ; DC et DMZ → autres zones
internes bloqué ; **ADM → tout** (seul chemin vers la base en 5432/22) ; LAN, DC, DMZ → Internet en 80/443 uniquement.
Zone SOC (ajoutée par `infra/fw_zone_soc.py`) : LAN, DC, DMZ → siem-elk-01 en 8220/9200 ; SOC → DNS/NTP de fw-01
et Internet en 80/443 ; **SOC → zones internes bloqué** (le SIEM reçoit, il n'initie rien) ; hôte Proxmox
(192.168.100.1, côté WAN) → siem-elk-01 en 22/5601 pour l'administration et Kibana.
Les journaux fw-01 partent en syslog UDP 514 vers bastion-01, collectés par l'intégration pfSense/OPNsense
(`logs-pfsense.log-default`). Configuration générée par `infra/fw_config.py`.

**Base clients.** PostgreSQL 17 + pgaudit (`read,write`, `log_relation`), journaux en UTC, base `core_clients`
(5000 clients), compte `c_dupont` en lecture seule. Collecte par l'intégration *Custom Logs (filestream)*,
dataset `db.audit`, avec l'ingest pipeline `db-audit-pgaudit` (`infra/pipeline_db_audit_pgaudit.json`) qui produit
`event.action` (`select`, `insert`, `update`, `delete`, `export` pour un `COPY ... TO`), `object` (table sans schéma),
`user.name`, `source.ip`, `db.statement`. Résultat : `logs-db.audit-default`, couvert par les règles `logs-db.audit-*`.

**Test de bout en bout validé.** 600 `SELECT` puis un `COPY clients TO STDOUT` depuis le bastion, en `c_dupont` :
601 documents dans `logs-db.audit-default` (600 `select`, 1 `export`, `source.ip` 10.0.5.10), alerte
« Lecture massive base clients » levée sur `c_dupont`.

**Annuaire.** Forêt `azurbank.local` (NetBIOS `AZURBANK`), OU Agences, Siege, Administrateurs, Serveurs ;
comptes c.dupont, m.bernard, s.leroy, adm.fontaine (admin du domaine). Audit des ouvertures de session,
de la gestion des comptes et groupes, de Kerberos et de la création de processus. Sysmon (config SwiftOnSecurity)
et Elastic Agent (System, Windows, Elastic Defend) installés sur srv-dc01 et ws-agence.

**Bastion.** Comptes adm.fontaine et c.dupont, SSH par clé ou mot de passe + TOTP (`pam_google_authenticator nullok` :
un compte sans TOTP enrôlé passe sans MFA, ce qui correspond au scénario de la démo).

Politiques Fleet créées par `infra/creer_politiques.py` (clé lue dans `ES_API_KEY`, `KB_URL` et `ES_CA` on-prem),
Elastic Defend compris dans `pol-windows`. Agents Elastic 9.5.6.
Les mots de passe du lab sont transmis à part, pas dans ce dépôt.

## SIEM on-prem : siem-elk-01 (6 novembre 2026)

Pourquoi : l'essai Elastic Cloud expire le 19 novembre. La **licence Basic** d'Elastic est gratuite et sans date
de fin ; elle couvre Elasticsearch, Kibana, Fleet, Elastic Defend (prévention malware), le moteur de détection
(règles Query, Threshold, EQL, ES|QL, Indicator match), les règles prébuilt, Timeline, Cases, TLS et comptes/rôles.
Elle ne couvre pas : la suppression d'alertes, le machine learning, les connecteurs externes (webhook, mail, Jira,
seuls *Index* et *Server log* restent), le SSO SAML/OIDC, et les Workflows/IA de la version cloud.
D'où la variante de règles `../03 - Détection (use case et règles)/regles/elastic-basic/` (sans `alert_suppression`, sans `destination.ip` dans l'ES|QL :
le pipeline pgaudit ne produit pas ce champ, seules les données de démo l'ont).

Résultat vérifié le 6 novembre : licence `basic` active, Fleet Server `HEALTHY`, 6 agents `online`
(les 5 machines du lab + siem-elk-01), data streams System, Windows/Sysmon, Elastic Defend, pfSense et `db.audit` alimentés.
Exfiltration rejouée depuis le bastion (600 `SELECT` + `COPY clients TO STDOUT` en `c_dupont`) : une alerte par
règle sur `c_dupont` (Threshold, EQL avec ses 101 événements « building block », ES|QL), confirmé par un second essai
après le réglage de l'ES|QL décrit dans `../03 - Détection (use case et règles)/FICHE_REGLES.md`.

### Accéder à Kibana

Kibana est sur https://10.40.0.10:5601, joignable seulement depuis l'hôte Proxmox. Depuis un PC qui a accès au Proxmox :

```bash
ssh -L 5601:10.40.0.10:5601 root@100.106.21.10      # laisser ouvert
# puis navigateur : https://localhost:5601  (compte elastic, mot de passe dans Accès lab (confidentiel, ne pas partager)/mots-de-passe-lab.xlsx)
```
Le certificat est signé par la CA du SOC (« Azur Bank SOC CA ») : le navigateur avertit tant qu'on n'a pas importé
`/root/elastic/pki/ca/ca.crt` de siem-elk-01. Shell sur la VM : `ssh -J root@100.106.21.10 jakub@10.40.0.10` (puis `sudo -i`).

### Refaire l'installation, étape par étape

Tous les scripts sont dans `infra/siem-elk-01/`. Les secrets générés restent sur la VM
(`/root/elastic/secrets.txt`, root seul) et sont recopiés dans `Accès lab (confidentiel, ne pas partager)/mots-de-passe-lab.xlsx`.

1. **Réseau (hôte Proxmox).** Bridge `vmbr6` sans IP dans `/etc/network/interfaces` (`ifreload -a`), une 6e carte
   sur fw-01 (`qm set 200 --net5 virtio,bridge=vmbr6`, à chaud), route vers la zone SOC par le WAN de fw-01
   (`post-up ip route add 10.40.0.0/24 via 192.168.100.2` sous `vmbr1`).
2. **Pare-feu.** `python3 fw_zone_soc.py config-actuelle.xml config-soc.xml` puis copie dans `/conf/config.xml` de fw-01
   et `/usr/local/etc/rc.reload_all`. Sauvegarde avant changement : `/conf/backup/config-avant-soc.xml` sur fw-01 et
   `/root/fw-config-avant-soc-20261106.xml` sur l'hôte. fw-01 est joignable en SSH depuis le bastion (ADM → tout).
3. **VM.** Image Debian 13 *genericcloud* importée en disque, cloud-init pour l'IP fixe, l'utilisateur et la clé SSH :
   ```bash
   qm create 220 --name siem-elk-01 --memory 10240 --cores 4 --cpu host --machine q35 --scsihw virtio-scsi-single \
     --net0 virtio,bridge=vmbr6 --agent 1 --serial0 socket --vga serial0 --onboot 1
   qm set 220 --scsi0 local:0,import-from=/var/lib/vz/template/qcow/debian-13-genericcloud-amd64.qcow2,discard=on,ssd=1
   qm resize 220 scsi0 80G
   qm set 220 --ide2 local:cloudinit --boot order=scsi0 --ciuser jakub --sshkeys /root/jakub.pub \
     --ipconfig0 ip=10.40.0.10/24,gw=10.40.0.1 --nameserver 10.40.0.1
   qm start 220
   ```
4. **Paquets.** Téléchargés sur l'hôte (`/var/lib/vz/elastic`, sommes SHA-512 vérifiées) depuis artifacts.elastic.co,
   version 9.5.6 (celle des agents), copiés dans `/root/elastic` de la VM.
5. **Elasticsearch + Kibana** : `install.sh`. Il règle `vm.max_map_count`, coupe le swap, installe Elasticsearch
   (la sécurité s'active seule : TLS sur 9200 et compte `elastic`), fixe le nom du cluster et le tas Java (4 Go),
   crée la CA du SOC et le certificat de la VM, installe Kibana en HTTPS, l'enrôle avec un jeton
   (`elasticsearch-create-enrollment-token -s kibana`) et génère les clés de chiffrement indispensables aux règles.
6. **Fleet Server** : `fleet-server.sh`. Déclare l'hôte Fleet Server `https://10.40.0.10:8220`, la politique
   `fleet-server-policy`, crée un jeton de service `elastic/fleet-server` et installe l'agent en mode Fleet Server.
   Contrôle : `curl --cacert /etc/azurbank-ca/soc-ca.crt https://10.40.0.10:8220/api/status` → `HEALTHY`.
7. **Politiques et pipeline.** Une clé API `soc-scripts`, puis le pipeline `db-audit-pgaudit`
   (`PUT _ingest/pipeline/db-audit-pgaudit` avec `infra/pipeline_db_audit_pgaudit.json`) et
   `KB_URL=https://10.40.0.10:5601 ES_CA=/root/elastic/pki/ca/ca.crt python3 creer_politiques.py`.
8. **Réenrôlement des agents** (sur l'hôte, jetons d'enrôlement et `soc-ca.crt` dans `/root/soc-enroll`) :
   `reenroler_linux.sh 210:<id pol-linux-db> 211:<id pol-linux-web> 212:<id pol-linux-bastion>` (par `pct`),
   `reenroler_windows.sh <id pol-windows> 201 202` (par l'agent invité QEMU). Chaque agent déjà installé reçoit
   `elastic-agent enroll --url=https://10.40.0.10:8220 --enrollment-token=... --certificate-authorities=soc-ca.crt --force` :
   il quitte le Fleet cloud et rejoint le Fleet on-prem sans réinstallation.
   Limite constatée le 12 novembre : sur Windows, Elastic Defend garde la clé de signature et la sortie du Fleet cloud
   (journal Endpoint : « signature verification failed ») et continue d'envoyer ses événements au cloud. Deux corrections :
   la sortie Fleet `default` du lab (préconfigurée dans `/etc/kibana/kibana.yml`) porte désormais le certificat
   `http_ca.crt` en plus de son empreinte, car Defend ignore l'empreinte seule ; et l'agent Windows est réinstallé
   (`reinstaller_windows.ps1` dans `/root/soc-enroll`, lancé par `winrun.sh` après remplacement du jeton et de la CA).
   Depuis, les événements `endpoint.events.*` de srv-dc01 et ws-agence arrivent sur le lab.
9. **Règles** (sur la VM) : `ES_URL=https://10.40.0.10:9200 KB_URL=https://10.40.0.10:5601 REGLES=elastic-basic
   ES_CA=<CA SOC + http_ca.crt concaténées> python3 ../03 - Détection (use case et règles)/regles/scripts/regles.py deploy`, puis `alerts` après le test.
   Raccourci sur la VM : `/root/elastic/regles.sh deploy|alerts|check`, et `/root/elastic/etat.sh` (agents + data streams).

## Bonus : Logstash et SOAR Shuffle (6 novembre 2026)

### Logstash : la passerelle SWIFT

La zone « DMZ partenaires » de l'énoncé (SWIFT, SEPA) n'a pas d'intégration Fleet toute faite : c'est le cas typique où
Logstash sert. Sur siem-elk-01, le pipeline `infra/logstash/swift-gateway.conf` écoute en TCP 5514, découpe la ligne
syslog (grok, puis kv), met les champs en ECS (`user.name`, `event.action`, `event.outcome`) et ajoute deux champs métier
avant l'indexation : `swift.correspondant_connu` (référentiel des BIC autorisés, filtre `translate`) et
`swift.hors_heures_ouvrees` (lundi-vendredi 7 h - 20 h, heure de Paris, filtre `ruby`). Sortie : `logs-swift.gateway-default`,
avec une clé API qui ne peut écrire que là.

La passerelle est simulée par `infra/bastion/sim_swift.py` sur bastion-01 (timer systemd `infra/bastion/sim-swift.timer`,
5 messages toutes les 5 min en jours ouvrés). `sim_swift.py --attaque` ajoute un MT103 de 2,4 M EUR vers un correspondant
inconnu : la règle « Virement SWIFT anormal » (`../03 - Détection (use case et règles)/regles/elastic-basic/query_swift_virement_anormal.json`, version Sigma
`../03 - Détection (use case et règles)/regles/sigma/swift_virement_anormal.yml`) lève une alerte critique. Testé le 6 novembre.

Refaire : paquet `logstash-9.5.6-amd64.deb` dans `/root/elastic` de la VM, puis `bash infra/logstash/install_logstash.sh`.

### Shuffle : la phase 2 SOAR

Shuffle 2.3.0 (open source, Docker) tourne sur soar-shuffle-01. En licence Basic, Kibana ne peut pas appeler de webhook :
c'est donc Shuffle qui lit les alertes par l'API, toutes les minutes. Le playbook « Azur Bank - Réponse exfiltration et fraude
SWIFT » a 4 nœuds Python (`../04 - Réponse à incident et SOAR/soar-shuffle-01/playbook/`) :

1. `lire_alertes` : alertes ouvertes des règles du use case et SWIFT, pas encore étiquetées `soar-traite`, regroupées par compte.
   Une condition arrête l'exécution s'il n'y a rien.
2. `ouvrir_case` : un case Kibana par incident, avec ses alertes attachées.
3. `reponse` : confinement. Rôle PostgreSQL en `NOLOGIN` et sessions coupées, compte AD désactivé (convention
   `c_dupont` → `c.dupont`), IP source ajoutée à l'alias `BLOCKLIST_SOAR` de fw-01 si elle est externe.
   Ce nœud ne fait rien tant que la variable `actions_actives` du workflow ne vaut pas `oui`.
4. `cloturer` : bilan des actions en commentaire du case, alertes passées en *acknowledged* avec l'étiquette `soar-traite`.

Testé le 6 novembre. En simulation : 2 cases (exfiltration c_dupont, virement SWIFT c.dupont) et 10 alertes acquittées.
En réel : exfiltration rejouée à 17:16 UTC, puis dans la minute un case Kibana, le rôle `c_dupont` en `NOLOGIN`, `c.dupont`
désactivé dans l'AD, et l'IP du bastion (interne) non bloquée, comme prévu. Le blocage d'IP a été testé à part
(203.0.113.50 ajoutée puis retirée de `BLOCKLIST_SOAR`). Une alerte qui arrive après coup (l'ES|QL) rejoue le confinement
sur le même case : c'est voulu. Pour remettre le compte en état après une démo : `bash /root/soc-enroll/reinitialiser_demo.sh`
sur l'hôte (script `../04 - Réponse à incident et SOAR/soar-shuffle-01/reinitialiser_demo.sh`).

**Comptes de service du SOAR (moindre privilège).**

| Où | Compte | Droits | Script |
|---|---|---|---|
| Elastic | `svc-shuffle` (clé API) | rôle `soar_shuffle` : lire et annoter les alertes, gérer les cases | `../04 - Réponse à incident et SOAR/soar-shuffle-01/compte_elastic_shuffle.sh` |
| db-clients-01 | `svc-shuffle` (clé SSH, sans mot de passe) | sudo sur `/usr/local/sbin/soar-verrou-db.sh` seulement (`postgres` protégé) | `../04 - Réponse à incident et SOAR/db-clients-01/soar-verrou-db.sh` |
| srv-dc01 | `AZURBANK\svc.shuffle` | Opérateurs de compte (désactive les utilisateurs, pas les admins), seul membre de `GG_SOAR_SSH` autorisé par sshd, SSH ouvert à 10.40.0.20 seulement dans le pare-feu Windows | `../04 - Réponse à incident et SOAR/srv-dc01/soar_compte_ssh.ps1` |
| fw-01 | `svc-shuffle` (clé API) | privilège « Diagnostics: PF Table IP addresses » : ajouter ou retirer une IP de `BLOCKLIST_SOAR`, rien d'autre (vérifié : 403 sur les autres API) | `../04 - Réponse à incident et SOAR/fw_shuffle.py` |

**Pare-feu pour le SOAR** (`../04 - Réponse à incident et SOAR/fw_shuffle.py`, appliqué le 6 novembre ; sauvegarde `/conf/backup/config-avant-shuffle.xml`
sur fw-01) : `BLOCKLIST_SOAR` bloqué en tête (entrée WAN et sortie de chaque zone) ; soar-shuffle-01 → fw-01 443 et
→ srv-dc01 / db-clients-01 22 ; hôte Proxmox → soar-shuffle-01 3443. La clé API OPNsense se crée sur fw-01 par
`createKey("svc-shuffle")` (voir l'en-tête du script). Les IP ajoutées par l'API vivent dans la table pf et disparaissent
au prochain rechargement complet de fw-01 : c'est un blocage d'urgence, à confirmer par une règle si l'incident le justifie.

Refaire : `bash "04 - Réponse à incident et SOAR/soar-shuffle-01/install.sh"` sur la VM (secrets générés dans `/root/shuffle-secrets.txt`), puis
`python3 creer_workflow.py playbook /root/shuffle-vars.txt`. Ce fichier de variables contient `es_url`, `kb_url`,
`es_api_key`, `ca_soc=@/root/ca-soc.pem`, `actions_actives`, `ssh_key_soar=@/root/soar_ed25519`, `ad_password`,
`opn_key` et `opn_secret`. Pour ouvrir l'interface : `ssh -L 3443:10.40.0.20:3443 root@100.106.21.10`, puis https://localhost:3443.

## VMs Proxmox (plan initial)

| VM | OS | vCPU / RAM / disque | Rôle | Logs |
|---|---|---|---|---|
| fw-01 | OPNsense | 2 / 2 Go / 16 Go | Routage inter-zones, NAT | Firewall (syslog → agent du bastion) |
| srv-dc01 | Windows Server 2022 eval | 2 / 4 Go / 60 Go | AD `azurbank.local` | Security, Sysmon |
| ws-agence | Windows 11 eval | 2 / 4 Go / 60 Go | Poste guichetier | Sysmon, Defender, Elastic Defend |
| db-clients-01 | Debian 13 | 2 / 2 Go / 20 Go | Base clients PostgreSQL + pgaudit | db.audit (use case) |
| web-portail-01 | Debian 13 | 1 / 1 Go / 10 Go | Portail web nginx | nginx.access |
| bastion-01 | Debian 13 | 1 / 1 Go / 10 Go | Jump host SSH | auth (system.auth) |

Total ≈ 10 vCPU / 14 Go RAM. Minimum viable si serré : db + web + bastion (4 Go).

## Étapes

### 1. Réseau Proxmox
Créer `vmbr2` à `vmbr5` (bridges sans IP physique), une interface de fw-01 sur chacun
+ une sur `vmbr1` (WAN, NAT de l'hôte). Règles fw : LAN → DMZ 443, LAN/ADM → DC selon besoin,
**seul ADM peut joindre db-clients-01 en 5432/22** (logique bancaire), tout → Internet 443.

### 2. Fleet : créer les politiques d'agent
Kibana → *Fleet* (ou Plus → Gestion → Fleet) → **Agent policies** → créer :

| Politique | Intégrations à ajouter |
|---|---|
| `pol-linux-db` | System, PostgreSQL (logs) |
| `pol-linux-web` | System, Nginx |
| `pol-linux-bastion` | System (auth.log), Custom UDP/Syslog (logs fw-01) |
| `pol-windows` | System, Windows, Elastic Defend |

Puis *Add agent* sur la politique → Kibana affiche la commande d'install avec
`--url=` (le Fleet managé) et `--enrollment-token=`. À copier sur la VM :

```bash
curl -L -O https://artifacts.elastic.co/downloads/beats/elastic-agent/elastic-agent-<VERSION>-linux-x86_64.tar.gz
tar xzvf elastic-agent-<VERSION>-linux-x86_64.tar.gz
cd elastic-agent-<VERSION>-linux-x86_64
sudo ./elastic-agent install --url=<FLEET_URL> --enrollment-token=<TOKEN>
```
(La version et l'URL exactes sont fournies par Kibana : toujours copier sa commande.)

### 3. db-clients-01 : PostgreSQL + pgaudit
```bash
sudo apt update && sudo apt install -y postgresql postgresql-17-pgaudit
sudo -u postgres psql -c "ALTER SYSTEM SET shared_preload_libraries = 'pgaudit';"
sudo -u postgres psql -c "ALTER SYSTEM SET pgaudit.log = 'read,write';"
sudo -u postgres psql -c "ALTER SYSTEM SET log_line_prefix = '%m [%p] %u@%d %h ';"
sudo systemctl restart postgresql
sudo -u postgres psql -c "CREATE DATABASE core_clients;"
sudo -u postgres psql -d core_clients -c "CREATE EXTENSION pgaudit;
  CREATE TABLE clients(id serial primary key, nom text, iban text, solde numeric);
  INSERT INTO clients(nom,iban,solde) SELECT 'client_'||g, 'FR76'||lpad(g::text,23,'0'), random()*10000 FROM generate_series(1,5000) g;
  CREATE USER c_dupont PASSWORD '<MOT_DE_PASSE_LAB>'; GRANT SELECT ON clients TO c_dupont;"
```
Les lignes `AUDIT: SESSION,...` arrivent dans `/var/log/postgresql/*.log`, collectées
par l'intégration PostgreSQL. **Simulation de l'exfiltration** (depuis le bastion) :
```bash
for i in $(seq 1 600); do echo "SELECT * FROM clients WHERE id=$i;"; done \
  | PGPASSWORD='<MOT_DE_PASSE_LAB>' psql -h 10.10.1.20 -U c_dupont -d core_clients >/dev/null
```
> En réel, le champ `object` / `event.action` n'est pas extrait tel quel par l'intégration :
> ajouter un *ingest pipeline* (processeur dissect sur `AUDIT: SESSION,...`) ou adapter la
> règle aux champs produits. C'est un bon point « normalisation » pour la partie B.

### 4. web-portail-01 : nginx
```bash
sudo apt install -y nginx
```
Logs `/var/log/nginx/access.log` → intégration Nginx. Test SQLi depuis une autre VM :
`curl "http://10.30.0.10/compte?id=1'%20OR%20'1'='1"`.

### 5. bastion-01
SSH avec clés + MFA (`libpam-google-authenticator`), seul point d'accès vers la zone DC.
Recevoir les syslogs de fw-01 en UDP 514 via l'intégration Custom UDP.

### 6. Windows (optionnel mais apprécié)
Installer Sysmon (config SwiftOnSecurity) + agent `pol-windows`. Joindre ws-agence au domaine.

## Données de démo déjà injectées

`"03 - Détection (use case et règles)/scripts/gen_logs_banque.py"` remplit trois data streams avec 24h de logs réalistes :
`logs-db.audit-banque`, `logs-nginx.access-banque`, `logs-bastion.auth-banque`.
Scénarios : exfiltration `c.dupont` (≈600 lectures + export), SQLi `45.146.165.37`,
brute force bastion `91.240.118.172` sur `adm.fontaine`.

```bash
export ES_URL="https://<projet>.es.<region>.gcp.elastic.cloud:443"
export ES_API_KEY="<votre clé>"
python3 "03 - Détection (use case et règles)/scripts/gen_logs_banque.py" --attack-now   # rejoue l'exfiltration pour une démo live
```
