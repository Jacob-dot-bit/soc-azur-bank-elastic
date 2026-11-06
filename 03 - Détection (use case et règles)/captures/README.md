# Captures : détection (partie C)

Prises le 6 novembre 2026 sur le SIEM on-prem.

| Fichier | Ce qu'elle montre |
| --- | --- |
| `alerte-exfiltration-c_dupont.png` | Security > Alertes : l'alerte « Lecture massive base clients puis export » du 6/11 à 18:16:26 (critique, risque 99), avec son motif (`c_dupont` depuis 10.0.5.10 sur db-clients-01). Elle est close : l'incident a été traité, voir `../../04 - Réponse à incident et SOAR/PARTIE_D_TRIAGE_ET_TICKET_5W.md` |
| `regle-eql-exfiltration.png` | Détail de la règle EQL : requête `sequence by user.name`, mapping MITRE (TA0009, TA0010, T1530), planification chaque minute |
| `regle-threshold-exfiltration.png` | Détail de la règle Threshold « Lecture massive base clients » (500 lectures par `user.name` en 10 min) |
