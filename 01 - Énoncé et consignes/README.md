# Énoncé et consignes

Les PDF de l'énoncé et du cours (ESGI, 5e année, module SOC RUN) restent dans le dossier du groupe et ne sont pas publiés ici.

## Résumé de l'énoncé (groupe 3, Elastic Security)

Le client est une banque de 1 500 personnes, présente sur plusieurs sites à l'international et soumise à PCI DSS, SWIFT CSP
et SEPA. Le groupe propose une solution SIEM complète jusqu'à son intégration, puis la présente en soutenance (30 min).

Les 11 points imposés : présentation de la solution, comparaison avec Splunk, QRadar et Microsoft Sentinel, architecture
stable et scalable On-Prem + Cloud, justification du choix, sources de logs, conformité bancaire, use case sensible
(imposé : **exfiltration de données clients**), règles de détection en Sigma et en format natif, deuxième phase avec un
SOAR, tableau de bord pour la direction, coût (licence, intégration, support).

Où chaque point est traité dans ce dépôt :

| Point | Où |
| --- | --- |
| 3. Architecture On-Prem + Cloud | `../02 - Architecture et infra/INFRA.md`, `../02 - Architecture et infra/schemas/` |
| 5. Sources de logs | `../02 - Architecture et infra/VISITE_GUIDEE.md` (un maillon par source) |
| 7. Use case | `../03 - Détection (use case et règles)/FICHE_REGLES.md` |
| 8. Règles Sigma + Elastic | `../03 - Détection (use case et règles)/regles/` |
| 9. SOAR | `../04 - Réponse à incident et SOAR/` |
| 1, 2, 4, 6, 10, 11 | `../05 - Soutenance (slides, dashboard, coût)/` |
