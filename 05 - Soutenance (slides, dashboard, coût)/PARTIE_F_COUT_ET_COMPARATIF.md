# Partie F : coût et comparatif des SIEM pour Azur Bank

Projet SOC RUN, ESGI 5A. Banque fictive Azur Bank : 1 500 collaborateurs, plusieurs sites, soumise à PCI DSS, SWIFT CSP et SEPA. Solution retenue : Elastic Security.

Relevé des prix : 6 novembre 2026. Tous les prix éditeurs sont en dollars US hors taxes. Conversion retenue : **1 $ = 0,86 €** (hypothèse de travail, à recaler sur le cours du jour de la soutenance).

---

## 1. Hypothèses de dimensionnement

### 1.1 Volume d'ingestion retenu : 100 Go/jour

Le coût de tous les SIEM du marché dépend d'abord du volume de logs. On l'estime source par source, après filtrage à la collecte (Logstash et politiques Fleet qui écartent le bruit : événements Windows de faible valeur, health checks HTTP, etc.).

| Source (zone bancaire) | Quantité | Volume unitaire estimé | Total / jour |
|---|---|---|---|
| Postes de travail (Elastic Defend + journaux Windows filtrés) | 1 500 | ~30 Mo | ~45 Go |
| Serveurs Windows / Linux (AD, fichiers, applicatifs) | ~200 | ~100 Mo | ~20 Go |
| Pare-feu, proxy, VPN (périmètre et inter-zones) | ~10 équipements | ~1,5 Go | ~15 Go |
| Contrôleurs de domaine (Kerberos, 4624/4625/4768…) | 4 | ~1 Go | ~4 Go |
| Bases de données clients (audit des SELECT, exports) | ~10 | ~0,5 Go | ~5 Go |
| Portail web / WAF / nginx | ~6 | ~0,5 Go | ~3 Go |
| Bastion d'administration | 2 | ~0,5 Go | ~1 Go |
| Passerelle SWIFT et flux SEPA | 2 | ~0,5 Go | ~1 Go |
| Microsoft 365 / Entra ID, EDR, antivirus, DNS | — | — | ~6 Go |
| **Total retenu** | | | **≈ 100 Go/jour** |

- Croissance supposée : **+10 % par an** (100, 110 puis 121 Go/jour).
- Équivalence en événements par seconde (utile pour QRadar) : avec un événement moyen de 500 octets, 100 Go/jour ≈ **2 300 EPS en moyenne, 5 000 EPS en pointe**.
- Sensibilité : à 50 Go/jour les coûts de licence à l'usage sont divisés par deux environ ; à 200 Go/jour ils doublent, avec des paliers de remise chez Splunk et Sentinel.

### 1.2 Rétention imposée par la conformité

| Exigence | Ce qu'elle impose au SIEM |
|---|---|
| PCI DSS v4.0.1, exigence 10.5.1 | conserver l'historique des journaux **au moins 12 mois**, dont **3 mois immédiatement consultables** |
| SWIFT CSP (CSCF, contrôle 6.4 « Logging and Monitoring ») | journaliser l'environnement SWIFT sécurisé, conserver et protéger les traces (on retient 12 mois) |
| DORA (règlement UE 2022/2554, applicable depuis le 17/01/2025) | détection et classification des incidents TIC, registre des prestataires TIC tiers (le SIEM cloud y figure) |

On retient donc **90 jours en données chaudes et 365 jours au total** pour toutes les solutions.

### 1.3 Périmètre du calcul

Trois ans (durée classique d'un contrat SIEM), en distinguant : licence ou consommation, infrastructure, intégration (projet de mise en œuvre), support éditeur, formation et personnel.

---

## 2. Comparatif Splunk / QRadar / Elastic / Sentinel

| Critère | **Elastic Security** | **Splunk Enterprise Security** (Cisco) | **IBM QRadar SIEM** | **Microsoft Sentinel** |
|---|---|---|---|---|
| Modèle de licence | Gratuit en licence Basic. Cloud Serverless : à l'usage, par Go ingéré + par Go conservé/mois, plus de frais par terminal depuis le 23/03/2026. Cloud Hosted : par ressources (RAM/stockage). Auto-hébergé : par nœud / RAM, prix non public | Par Go/jour ingéré (licence annuelle) ou par « workload » (SVC). Enterprise Security est une ligne en plus, vendue à partir de 50 Go/jour | Par EPS (événements/s) et FPM (flux/min). Prix non public | À l'usage par Go ingéré (paiement à l'usage ou paliers d'engagement de 50 à 50 000 Go/jour) |
| Déploiement | On-prem, cloud (Elastic Cloud sur AWS, GCP, Azure, régions UE) **et hybride** (agents et Logstash on-prem, recherche inter-clusters) | On-prem (Splunk Enterprise) ou cloud (Splunk Cloud) | On-prem (appliances ou logiciel). **L'offre SaaS a été cédée à Palo Alto Networks le 4/09/2024** ; QRadar on Cloud est en fin de vie depuis le 14/04/2026, migration vers Cortex XSIAM | **Cloud uniquement** (Azure). L'on-prem est collecté par agents (AMA) ou forwarders |
| SIEM | Moteur de détection (KQL, EQL, ES\|QL, seuils, ML), +1 000 règles prêtes, MITRE ATT&CK | Très complet (SPL), large catalogue d'apps et de contenus | Corrélation (règles et « offenses »), AQL, bon support réseau (QFlow) | Règles analytiques KQL (Kusto), UEBA, intégration native Defender et Entra |
| SOAR | Basic : cases + Shuffle open source (notre lab). Payant : connecteurs ServiceNow/Jira, actions de réponse sur l'hôte, Elastic Workflows | Splunk SOAR, produit séparé, sur devis (inclus dans l'édition Premier) | QRadar SOAR, produit séparé (2 utilisateurs : 22 704 $/an sur AWS Marketplace) | Playbooks Logic Apps + règles d'automatisation, facturés à l'action |
| Conformité | Tableaux de bord et rapports à construire ; rétention longue économique (snapshots consultables, niveau froid/frozen) ; données hébergeables 100 % on-prem | Apps de conformité PCI (payantes), très mature | Packs de conformité PCI fournis, historique bancaire fort | Classeurs (workbooks) PCI DSS fournis ; données en région Azure UE ; rétention longue via niveau archive / data lake |
| Compétences requises | KQL/EQL/ES\|QL, exploitation Elasticsearch si auto-hébergé ; communauté open source large | SPL, profils nombreux sur le marché et bien payés | AQL, profils rares et en recul | KQL Kusto (différent du KQL de Kibana), Azure, écosystème Microsoft |
| Forces | Coût, ouverture (open source, format ECS), hybride natif, aucun verrou | Maturité, écosystème, puissance de recherche | Corrélation réseau, présence historique en banque | Intégration Microsoft 365 / Defender, sources Microsoft gratuites, zéro infrastructure |
| Faiblesses | Fonctions avancées (ML, actions de réponse, frozen) réservées aux offres payantes ; demande de l'expertise si auto-hébergé | **Le plus cher** à volume égal ; ES et SOAR facturés en plus | **Feuille de route incertaine** depuis la cession du SaaS ; coût matériel | Coût élevé au Go hors sources Microsoft ; dépendance à Azure ; pas d'on-prem |

Lecture : les quatre outils savent répondre techniquement à PCI DSS et SWIFT CSP. Ce qui les sépare pour Azur Bank, c'est le coût à 100 Go/jour, la possibilité de garder les zones sensibles (SWIFT, données de carte) on-prem, et la pérennité de l'éditeur.

---

## 3. Coût de notre lab (fait, gratuit)

| Poste | Solution du lab | Coût |
|---|---|---|
| SIEM | Elasticsearch + Kibana + Fleet Server 9.5.6, licence **Basic**, VM siem-elk-01 | 0 € (licence gratuite, sans limite de durée) |
| Collecte | 5 Elastic Agents via Fleet + Logstash (passerelle SWIFT simulée) | 0 € |
| SOAR | Shuffle 2.3.0 open source (VM soar-shuffle-01) : case Kibana, NOLOGIN PostgreSQL, désactivation AD, blocage IP sur OPNsense | 0 € |
| Pare-feu | OPNsense | 0 € |
| Poste Windows 11 | version d'évaluation (jusqu'au 4/02/2027) | 0 € |
| Cloud | essai Elastic Serverless (14 jours, fin vers le 19/11/2026) pour la partie cloud de l'hybride | 0 € |
| Matériel | serveur Proxmox déjà disponible | 0 € d'achat |
| Électricité | hypothèse ~120 W en continu, ~0,20 €/kWh | ≈ 17 €/mois, ≈ 630 € sur 3 ans |

**Total licences du lab : 0 €.** Ce que le lab ne couvre pas et que la production doit payer : haute disponibilité (un seul nœud), machine learning et suppression d'alertes (d'où nos règles en variante « elastic-basic »), connecteurs ServiceNow/Jira natifs, actions de réponse sur l'hôte, stockage frozen pour 12 mois de rétention, support éditeur.

---

## 4. Cible de production recommandée : Elastic en hybride

**Architecture** (voir [le schéma d'architecture hybride](../02%20-%20Architecture%20et%20infra/schemas/architecture-hybride.png)) :

- **On-prem** : Fleet Server (×2) et Logstash (×2) dans la zone SOC. Logstash filtre, enrichit et **masque les numéros de carte (PAN) avant tout envoi**, ce qui sort le cloud du périmètre des données de carte. Les zones SWIFT et PCI restent maîtrisées sur site. Shuffle (ou Elastic Workflows) pour le SOAR.
- **Cloud** : projet **Elastic Security Serverless, niveau Complete**, en région UE. Pas d'infrastructure à exploiter, UEBA, automatisation des workflows et connectivité privée inclus.
- Alternative 100 % on-prem si la direction refuse le cloud : Elastic auto-hébergé **Enterprise** (voir 5.2).

### 4.1 Consommation Elastic Serverless Complete (prix publics)

Tarifs publics (elastic.co/pricing/serverless-security, en vigueur depuis le 1/11/2025) : **ingestion à partir de 0,11 $/Go**, **rétention à partir de 0,019 $/Go/mois**, 50 Go de sortie gratuits puis 0,05 $/Go. Ces prix sont des planchers (« as low as ») : on applique **une marge de ×1,5** pour le budget.

| Année | Volume/jour | Ingestion | Rétention (montée en charge sur 365 j) | Total plancher | **Budget (×1,5)** |
|---|---|---|---|---|---|
| 1 | 100 Go | 4 015 $ | 4 161 $ | 8 176 $ | **12 264 $** |
| 2 | 110 Go | 4 416 $ | 8 738 $ | 13 155 $ | **19 733 $** |
| 3 | 121 Go | 4 858 $ | 9 612 $ | 14 470 $ | **21 705 $** |
| **3 ans** | | | | 35 801 $ | **53 701 $ ≈ 46 200 €** |

Calcul : ingestion = Go/jour × 365 × 0,11 $ ; rétention = Go conservés en moyenne sur l'année × 0,019 $ × 12 (le stock monte jusqu'à 365 jours de données, puis se stabilise).

### 4.2 Coût complet sur 3 ans (TCO)

| Poste | Année 1 | Année 2 | Année 3 | 3 ans | Statut du prix |
|---|---|---|---|---|---|
| Elastic Serverless Complete (budget ×1,5) | 10,5 k€ | 17,0 k€ | 18,7 k€ | **46 k€** | public |
| SOAR : Shuffle open source (ou Elastic Workflows, 10 000 exécutions gratuites puis 0,0108 $) | 0 | 0 | 0 | **0** | public |
| Infrastructure on-prem (VM Fleet, Logstash, Shuffle sur la virtualisation existante, quote-part) | 6 k€ | 6 k€ | 6 k€ | **18 k€** | estimation |
| Réseau (sortie de données, lien privé) | 1 k€ | 1 k€ | 1 k€ | **3 k€** | public (0,05 $/Go) |
| Intégration : build 100 jours puis 25 jours/an de maintien, à 900 €/jour (intégrateur) | 90 k€ | 22,5 k€ | 22,5 k€ | **135 k€** | fourchette marché (TJM 700 à 1 100 €) |
| Formation (Elastic Training, 5 personnes) | 10 k€ | 4 k€ | 4 k€ | **18 k€** | fourchette |
| Support éditeur | inclus | inclus | inclus | **0** | support standard inclus ; support premium sur devis |
| Personnel SOC interne (heures ouvrées) | 410 k€ | 410 k€ | 410 k€ | **1 229 k€** | voir 4.3 |
| Prestataire MSSP nuits et week-ends | 110 k€ | 110 k€ | 110 k€ | **330 k€** | non public, fourchette 80 à 150 k€/an |
| **Total** | **≈ 638 k€** | **≈ 571 k€** | **≈ 573 k€** | **≈ 1,78 M€** | |

### 4.3 Personnel (le vrai coût d'un SOC)

| Rôle | ETP | Salaire brut annuel retenu | Source de la fourchette |
|---|---|---|---|
| Ingénieur détection / SIEM (N3) | 1 | 70 k€ | N3 : 60 à 80 k€ (Recruteur Indépendant, 5/05/2026) ; 75 à 105 k€ (Optima Europe, 10/03/2026) |
| Analystes SOC N2 | 3 | 55 k€ | N2 : 45 à 62 k€ (Recruteur Indépendant) ; 52 à 75 k€ (Optima Europe) |
| Responsable SOC (mi-temps) | 0,5 | 95 k€ | Lead / Manager : 95 à 130 k€ (Optima Europe) |
| **Total brut** | 4,5 | **282,5 k€** | |
| **Coût employeur** (charges patronales ≈ 45 %) | | **≈ 410 k€/an** | |

Un SOC interne 24 h/24 demanderait environ 10 analystes (5 à 6 ETP par poste tenu en continu) ; le modèle mixte « équipe interne en journée + MSSP la nuit » est le plus courant pour une banque de cette taille.

**Ce qu'il faut retenir : la licence Elastic pèse moins de 3 % du coût total sur 3 ans. Le personnel en pèse près de 90 %.**

---

## 5. Même calcul pour les concurrents

On compare à périmètre égal : 100 Go/jour (+10 %/an), 12 mois de rétention. Le personnel est le même pour tous (environ 1,56 M€ sur 3 ans) et n'apparaît donc pas ci-dessous ; seules la licence, l'infrastructure propre à chaque solution et l'intégration changent.

### 5.1 Licence ou consommation sur 3 ans

| Solution | Base de calcul | 3 ans | Nature du prix |
|---|---|---|---|
| **Elastic Serverless Complete** | 0,11 $/Go + 0,019 $/Go/mois, ×1,5 | **54 k$** | public (elastic.co) |
| **Elastic auto-hébergé Enterprise** | ~6 unités de ressources (64 Go de RAM chacune : 4 nœuds chauds, 1 frozen, 1 ML), 10 à 20 k$ l'unité/an | **180 à 360 k$** | **non public** (« contact sales »), fourchette |
| **Microsoft Sentinel** | palier 100 Go/jour à 296 $/jour (2,96 $/Go, dépassement au même tarif) + archive 0,02 $/Go/mois au-delà de 90 j | **375 k$** | tarif catalogue Azure East US relevé par un tiers |
| **Splunk Cloud + Enterprise Security** | palier 100-199 Go/jour : 1 012 $ + 759 $ par Go/jour et par an | **586 k$** (+ SOAR sur devis) | prix catalogue G-Cloud 15 (janvier 2026) relevé par un tiers |
| **Splunk Enterprise (auto-hébergé) + ES** | 759 $ + 759 $ par Go/jour et par an | **502 k$** (+ matériel, + SOAR sur devis) | idem |
| **IBM QRadar SIEM on-prem** | 500 EPS = 12 074 $/an (AWS Marketplace) ; à 2 300 EPS moyen / 5 000 en pointe : 60 à 150 k$/an + QRadar SOAR 22 704 $/an (2 utilisateurs) | **250 à 520 k$** | **non public**, extrapolation |

Remarques :

- **Sentinel** baisse si Azur Bank a des licences Microsoft 365 E5 : Office 365 Audit, Azure Activity et les alertes Defender sont gratuits, et E5 offre 5 Mo/utilisateur/jour, soit 7,5 Go/jour pour 1 500 personnes (environ −7 %). Il faut aussi noter que le palier promotionnel à 50 Go/jour s'arrête le 31/12/2026.
- **Splunk** ne vend Enterprise Security qu'à partir de 50 Go/jour, et la ligne ES double presque la licence. Les prix négociés sont en général inférieurs au catalogue, mais restent les plus élevés du marché.
- **QRadar** : aucune grille publique. IBM continue de vendre l'on-prem, mais la cession du SaaS à Palo Alto Networks et la migration poussée vers Cortex XSIAM rendent un nouveau projet sur 5 ans risqué.

### 5.2 Total hors personnel sur 3 ans

| Solution | Licence | Infra propre | Intégration | **Total 3 ans** |
|---|---|---|---|---|
| **Elastic hybride (Serverless + collecte on-prem)** | 46 k€ | 21 k€ | 135 k€ | **≈ 200 k€** |
| Elastic auto-hébergé Enterprise | 155 à 310 k€ | ~120 k€ (6 à 8 serveurs, stockage) | 160 k€ | **435 à 590 k€** |
| Microsoft Sentinel | 323 k€ | ~20 k€ (collecteurs on-prem) | 135 k€ | **≈ 480 k€** |
| IBM QRadar on-prem | 215 à 450 k€ (SOAR compris) | 70 à 140 k€ (appliances) | 160 k€ | **445 à 750 k€** |
| Splunk Cloud + ES | 504 k€ (+ SOAR) | ~20 k€ | 150 k€ | **≈ 675 k€ et plus** |

Avec le personnel (~1,56 M€ sur 3 ans pour tous), le TCO va de **≈ 1,78 M€ (Elastic hybride)** à **≈ 2,2 M€ et plus (Splunk)**.

---

## 6. Justification du choix pour Azur Bank

1. **Coût** : à 100 Go/jour, la consommation Elastic Serverless coûte 7 fois moins que Sentinel et 11 fois moins que Splunk au prix catalogue. L'écart finance une partie de l'équipe SOC.
2. **Hybride natif** : la collecte, le filtrage et le masquage des PAN restent on-prem (zones SWIFT et PCI), le moteur de détection est dans le cloud UE. Sentinel est cloud uniquement ; QRadar n'a plus d'offre cloud chez IBM.
3. **Pas de verrou** : licence Basic gratuite, schéma ECS ouvert, règles exportables en SIGMA. On a pu tout prototyper gratuitement dans le lab, ce qui réduit le risque du projet.
4. **Pérennité** : éditeur indépendant, coté, offre en développement continu, contrairement à QRadar.
5. **Points de vigilance** : les fonctions avancées sont payantes (niveau Complete ou Enterprise) ; le prix auto-hébergé n'est pas public et doit être négocié ; il faut des compétences Elasticsearch en interne si on choisit l'on-prem pur.

---

## 7. Sources (consultées le 6/11/2026)

**Prix éditeurs (officiels)**

- Elastic, *Elastic Cloud Serverless pricing for Elastic Security* : https://www.elastic.co/pricing/serverless-security (tarifs en vigueur depuis le 1/11/2025 ; fin des frais par terminal au 23/03/2026)
- Elastic, *Elastic Cloud Hosted pricing* : https://www.elastic.co/pricing/cloud-hosted (Standard 99 $, Gold 114 $, Platinum 131 $, Enterprise 184 $ par mois au minimum)
- Elastic, *Subscriptions* (auto-hébergé, « contact sales ») : https://www.elastic.co/subscriptions
- Microsoft, *Microsoft Sentinel pricing* : https://www.microsoft.com/en-us/security/pricing/microsoft-sentinel (paliers d'engagement jusqu'à −52 %, palier 50 Go/jour promotionnel jusqu'au 31/12/2026)
- Microsoft, *Microsoft Sentinel benefit for Microsoft 365 E5* : https://azure.microsoft.com/en-us/pricing/offers/sentinel-microsoft-365-offer/
- Splunk by Cisco, *Pricing* : https://www.splunk.com/en_us/products/pricing.html (aucun prix SIEM publié, « contact us »)

**Relevés tiers (prix catalogue non publiés par l'éditeur)**

- SIEM Cost Calculator, *Splunk Pricing 2026* (mis à jour le 13/10/2026, d'après le catalogue UK G-Cloud 15 de janvier 2026) : https://siemcostcalculator.com/splunk-pricing
- SIEM Cost Calculator, *IBM QRadar Pricing 2026* (mis à jour le 13/10/2026, listing AWS Marketplace vérifié le 7/09/2026) : https://siemcostcalculator.com/qradar-pricing
- SIEM Cost Calculator, *Microsoft Sentinel Pricing 2026* (mis à jour le 26/10/2026, tarifs Azure East US) : https://siemcostcalculator.com/sentinel-pricing

Ce site est sponsorisé par un éditeur de pipeline de logs ; ses chiffres sont recoupés avec les pages éditeurs quand c'est possible et doivent être confirmés par un devis.

**Salaires**

- Optima Search Europe, *Benchmark des salaires des analystes SOC en Europe* (10/03/2026) : https://www.optimaeurope.com/fr/recruitment-blog/benchmark-des-salaires-des-analystes-soc-en-europe
- Recruteur Indépendant, *Salaire analyste SOC en 2026* (5/05/2026) : https://recruteurindependant.com/salaire-analyste-soc/

**Réglementation**

- PCI SSC, *PCI DSS v4.0.1*, exigence 10.5.1 (rétention 12 mois, 3 mois disponibles)
- SWIFT, *Customer Security Controls Framework* (CSCF), contrôle 6.4
- Règlement (UE) 2022/2554 (DORA)

---

## Résumé pour la slide

1. Hypothèse : 100 Go de logs par jour (+10 %/an), 12 mois de rétention dont 3 mois chauds (PCI DSS 10.5.1).
2. Lab : 0 € de licence (Elastic Basic + Logstash + Shuffle open source sur Proxmox).
3. Production : Elastic Serverless Complete en hybride ≈ 46 k€ de consommation sur 3 ans, ≈ 200 k€ avec infra et intégration.
4. À périmètre égal, hors personnel : Sentinel ≈ 480 k€, QRadar 445 à 750 k€, Splunk ≈ 675 k€ et plus.
5. TCO 3 ans ≈ 1,8 M€, dont près de 90 % de personnel : le choix d'Elastic finance l'équipe plutôt que la licence.
