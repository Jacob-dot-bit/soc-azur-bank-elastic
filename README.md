# Projet SOC RUN : Azur Bank avec Elastic Security

Groupe 3, ESGI 5A. Use case imposé : exfiltration de données clients (MITRE T1530 / TA0010).

Ce fichier correspond au document « 00 - LIRE EN PREMIER » du Google Drive. L'arborescence locale est la même que celle
du Drive (dossier `SOC_RUN`) :

| Dossier | Contenu |
| --- | --- |
| `01 - Énoncé et consignes/` | Énoncés du TP (Elastic, Splunk, QRadar, Sentinel) et supports de cours |
| `02 - Architecture et infra/` | `INFRA.md` (architecture, infra déployée, comment tout refaire), `VISITE_GUIDEE.md` (le lab maillon par maillon), `schemas/` (schémas drawio, png, svg et leur générateur), `infra/` (pare-feu OPNsense et zone SOC, politiques Fleet, pipeline pgaudit, ws-agence, SIEM `siem-elk-01/`, `logstash/`, simulateur SWIFT `bastion/`) |
| `03 - Détection (use case et règles)/` | `FICHE_REGLES.md` (fiche du use case et des règles), `regles/` (Sigma, Elastic Cloud, variante `elastic-basic/` et script de déploiement), `scripts/gen_logs_banque.py` (logs de démonstration) |
| `04 - Réponse à incident et SOAR/` | SOAR Shuffle `soar-shuffle-01/` (installation, playbook, remise à zéro de la démo), comptes de service (`db-clients-01/`, `srv-dc01/`) et règles fw-01 du SOAR (`fw_shuffle.py`) |
| `05 - Soutenance (slides, dashboard, coût)/` | Support de soutenance, tableau de bord direction, chiffrage |
| `99 - Archives/` | Versions remplacées |
| `Accès lab (confidentiel, ne pas partager)/` | `mots-de-passe-lab.xlsx` : tous les accès du lab (lisible par son propriétaire seul, exclu de git) |

Le SIEM tourne **on-prem** sur le Proxmox (siem-elk-01, 10.40.0.10, zone SOC) : Elasticsearch, Kibana et Fleet Server 9.5.6 en licence Basic, gratuite et sans date de fin. Logstash y ingère la passerelle SWIFT simulée, et Shuffle (soar-shuffle-01, 10.40.0.20) automatise la réponse : case Kibana, compte base et AD confinés, IP bloquée sur fw-01. Le projet Elastic Cloud illustre la partie Cloud de l'architecture hybride.

Par où commencer : `02 - Architecture et infra/VISITE_GUIDEE.md`.

Les scripts lisent la clé API Elastic dans la variable `ES_API_KEY`, jamais dans un fichier. Les mots de passe ne sont que dans `Accès lab (confidentiel, ne pas partager)/mots-de-passe-lab.xlsx` : ne pas le joindre aux livrables.
