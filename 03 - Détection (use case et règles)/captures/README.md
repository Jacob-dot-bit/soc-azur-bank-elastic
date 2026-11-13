# Captures : détection (partie C)

Prises le 6 novembre 2026 sur le SIEM on-prem.

| Fichier | Ce qu'elle montre |
| --- | --- |
| `alerte-exfiltration-c_dupont.png` | Security > Alertes : l'alerte « Lecture massive base clients puis export » du 6/11 à 18:16:26 (critique, risque 99), avec son motif (`c_dupont` depuis 10.0.5.10 sur db-clients-01). Elle est close : l'incident a été traité, voir `../../04 - Réponse à incident et SOAR/PARTIE_D_TRIAGE_ET_TICKET_5W.md` |
| `regle-eql-exfiltration.png` | Détail de la règle EQL : requête `sequence by user.name`, mapping MITRE (TA0009, TA0010, T1530), planification chaque minute |
| `regle-threshold-exfiltration.png` | Détail de la règle Threshold « Lecture massive base clients » (500 lectures par `user.name` en 10 min) |

Ajoutées le 13 novembre 2026 (SIEM du lab, tests des règles Active Directory, voir `../FICHE_REGLES.md`) :

| Fichier | Ce qu'elle montre |
| --- | --- |
| `alerte-ad-groupe-privilegie-test.soc.png` | Alerte « Ajout à un groupe privilégié Active Directory » (high, 73) : `test.soc` ajouté aux Admins du domaine sur srv-dc01, MITRE TA0003 / T1098.007 |
| `alerte-effacement-journal-srv-dc01.png` | Alerte « Effacement d'un journal d'événements Windows » (high, 73) : 1102 sur srv-dc01 après `wevtutil cl Security`, MITRE TA0112 / T1685.005 |
| `alerte-admin-hors-horaires-adm.fontaine.png` | Alerte « Connexion d'un compte administrateur hors heures ouvrées » (medium, 47) : SSH d'`adm.fontaine` sur bastion-01 à 02:13 (heure de Paris), MITRE TA0001 / T1078.002 |
