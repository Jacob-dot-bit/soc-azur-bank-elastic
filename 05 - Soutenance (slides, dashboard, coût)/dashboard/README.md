# Tableau de bord direction (COMEX)

Dashboard Kibana « Azur Bank - Tableau de bord direction (SOC) », construit sur les alertes du SIEM on-prem
(`.alerts-security.alerts-default`). Il répond à la question du COMEX : *sommes-nous attaqués, est-ce grave, réagissons-nous
vite, et sommes-nous en règle ?* Capture du 6 novembre 2026 : `dashboard_comex.png`.

| Indicateur | Ce qu'il mesure | Comment il est calculé |
| --- | --- | --- |
| Incidents ouverts (à traiter) | Posture : ce qui attend une décision | alertes au statut `open` |
| Incidents critiques (période) | Gravité | alertes de criticité `critical` |
| MTTD (min) | Rapidité de détection | moyenne de `@timestamp` - `kibana.alert.original_time` (champ calculé `mttd_minutes`) |
| MTTR (min) | Rapidité de prise en charge | moyenne de `kibana.alert.workflow_status_updated_at` - `@timestamp`, pour les alertes acquittées ou closes (`mttr_minutes`) |
| Incidents par criticité et par statut | Charge du SOC et retard éventuel | criticité × statut (open, acknowledged, closed) |
| Incidents par jour et par scénario | Tendance, scénario le plus actif | une barre par jour, une couleur par règle |
| Incidents par exigence réglementaire | Conformité PCI DSS et SWIFT CSP | étiquettes des règles (`PCI DSS`, `PCI DSS 6.4`, `PCI DSS 8.3`, `SWIFT CSP`, `SWIFT CSP 4.1`), champ calculé `conformite` |
| Faux positifs déclarés | Qualité des règles | alertes étiquetées `faux-positif` par l'analyste à la clôture (`faux_positif`) |
| Comptes les plus concernés | Où agir en priorité | top des `user.name` avec le score de risque maximal |

Les alertes « building block » (événements unitaires d'une séquence EQL) sont exclues : un incident = une alerte principale.

Lecture des chiffres du 6 novembre : 11 incidents critiques, tous issus des tests d'exfiltration et de fraude SWIFT ; MTTD
d'une minute (la règle tourne chaque minute) ; MTTR de 71 min en moyenne, tiré vers le haut par les alertes de la matinée,
traitées avant la mise en service du SOAR. Depuis Shuffle, la prise en charge tombe à environ une minute. Un faux positif est
déclaré : l'injection SQL de test lancée depuis le bastion (scanner autorisé).

Convention pour les analystes : à la clôture d'une alerte qui n'était pas une attaque, ajouter l'étiquette `faux-positif`
(Alerts > ... > *Apply alert tags*). C'est elle qui alimente l'indicateur de faux positifs.

## Importer ou recréer

- Import : Kibana > Stack Management > Saved objects > *Import* > `dashboard_comex.ndjson` (vue de données, 9 Lens et
  le dashboard).
- Recréer par script (sur siem-elk-01) :
  `KB_URL=https://10.40.0.10:5601 ES_CA=/root/elastic/pki/ca/ca.crt ES_API_KEY=... python3 creer_dashboard_comex.py dashboard_comex.ndjson`.
  Le script importe les objets (identifiants fixes, donc relançable) puis réexporte le ndjson.
