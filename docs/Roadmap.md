# 🗺️ ROADMAP - Monitor Agent IA

*Système de monitoring de sites web concurrents avec agent IA*

---

## Vue d'ensemble du projet

Ce projet implémente un système de surveillance automatique de sites web qui prend des instructions en langage naturel (ex: "surveille la page de prix de TechCorp pour les changements de tarifs"). Le système utilise un agent IA pour identifier l'URL correcte et les éléments à surveiller, scrape le site deux fois à ~24h d'intervalle avec Firecrawl, compare les versions et envoie une alerte Gmail uniquement en cas de changements significatifs.

---

## ⚙️ Décisions techniques finales

### Stack technologique retenu :
- **Agent IA** : CrewAI avec un seul agent + API Groq (modèle Mixtral/Llama)
- **Scraper** : Firecrawl uniquement
- **Scheduling** : n8n (workflow orchestration) + APScheduler (backup/fallback)
- **Multi-sites** : Fichier config YAML (3 sites max) - migration vers Sheets en Phase 5
- **Seuil de changement** : 1% par défaut, configurable par site

### Calcul du seuil de changement expliqué :

Le **seuil** détermine si un changement est "significatif" et mérite une notification.

**Formule :**
```
Score de changement = (Nombre de lignes modifiées / Nombre total de lignes) × 100
```

**Exemple concret :**
```
Contenu original (50 lignes) :
- Ligne 1: Plan Pro: $99/month
- Ligne 2: Plan Enterprise: Contact us
- ... (48 autres lignes)

Contenu nouveau (50 lignes) :
- Ligne 1: Plan Pro: $129/month  ← CHANGÉ
- Ligne 2: Plan Enterprise: Contact us
- ... (48 autres lignes)

Score = (1 ligne changée / 50 lignes total) × 100 = 2%
```

**Décision :**
- Si score > seuil (ex: 2% > 1%) → **Alerte envoyée** 🔔
- Si score ≤ seuil (ex: 0.5% ≤ 1%) → **Ignoré** (bruit/changement mineur)

**Pourquoi c'est important :**
- Éviter les faux positifs (ex: changement d'un timestamp → 0.1%)
- Focus sur les changements business-critical (prix, features, etc.)

### n8n : Comment ça marche ?

**n8n** = Outil d'automatisation no-code/low-code (alternative open-source à Zapier)

**Installation locale (recommandé pour apprendre) :**
```bash
# Option 1 : npx (le plus simple)
npx n8n

# Option 2 : Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Option 3 : npm global
npm install -g n8n
n8n start
```

**Workflow typique pour ce projet :**
```
[Cron Trigger]       ← Déclenche tous les jours à 10h
    ↓
[Execute Command]    ← Lance : python /path/to/main.py
    ↓
[HTTP Request]       ← (Optionnel) Appelle une API de votre script
    ↓
[If/Switch]          ← Vérifie si erreurs
    ↓
[Gmail/Slack]        ← Notification en cas d'erreur
```

**Pourquoi n8n :**
- Interface visuelle pour débugger
- Logs intégrés
- Peut appeler votre script Python via CLI
- Monitoring des exécutions
- Notifications d'erreurs
- Facile à étendre (webhooks, Slack, etc.)

**Alternative APScheduler :**
Si n8n est trop complexe au début, APScheduler sera notre fallback (tout en Python).

---

## Phase 1 : Architecture & Configuration (Fondations)

### 1.1 Structure du projet

```
monitor_agent/
├── config/
│   ├── .env.example          # Template des variables d'environnement
│   ├── settings.py            # Configuration centralisée
│   └── sites.yaml             # Configuration des 3 sites à surveiller
├── src/
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── ai_agent.py       # Agent IA (CrewAI + Groq)
│   │   ├── firecrawl_scraper.py  # Scraping avec Firecrawl
│   │   ├── content_comparator.py # Comparaison de contenus
│   │   ├── sheets_manager.py  # Gestion Google Sheets
│   │   └── gmail_notifier.py  # Notifications email
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py          # Logging personnalisé
│   │   └── validators.py      # Validation des données
│   └── main.py                # Point d'entrée principal
├── tests/
│   └── test_*.py              # Tests unitaires
├── data/
│   └── logs/                  # Logs d'exécution
├── n8n/
│   └── workflows/             # Workflows n8n (JSON)
├── requirements.txt
├── .env                       # Variables d'environnement (à ignorer)
├── .gitignore
├── Roadmap.md                 # Ce fichier
└── README.md
```

### 1.2 Services à configurer

- **Groq API** : Pour l'agent IA (modèles Mixtral/Llama)
- **CrewAI** : Framework d'orchestration d'agents
- **Firecrawl API** : Pour le scraping avancé (sites JavaScript)
- **Google Sheets API** : Pour le stockage des données
- **Gmail API** : Pour les notifications
- **n8n** : Orchestration de workflows et scheduling

---

## Phase 2 : Modules Core (Développement)

### 2.1 Module AI Agent (`ai_agent.py`)

**Responsabilités :**
- Interpréter les instructions en langage naturel
- Identifier l'URL cible à partir d'une description
- Déterminer les éléments spécifiques à surveiller
- Générer des sélecteurs CSS/XPath si nécessaire

**Exemple d'utilisation :**
```python
instruction = "surveille la page de prix de TechCorp pour les changements de tarifs"
→ URL: https://techcorp.com/pricing
→ Éléments: prix, plans, fonctionnalités
```

**Fonctionnalités clés :**
- Parsing d'instructions complexes
- Résolution d'URLs ambiguës
- Mémorisation du contexte (historique des surveillances)
- Validation des URLs extraites

---

### 2.2 Module Firecrawl Scraper (`firecrawl_scraper.py`)

**Responsabilités :**
- Appeler l'API Firecrawl avec authentification Bearer
- Extraire le contenu en Markdown ET HTML
- Gérer les erreurs (timeouts, rate limits)
- Nettoyer et normaliser le contenu

**Points techniques :**
- Gestion des sites JavaScript lourds
- Extraction de zones spécifiques si demandé
- Stockage du contenu brut pour comparaison
- Retry logic avec backoff exponentiel

**Configuration Firecrawl :**
```python
POST https://api.firecrawl.dev/v0/scrape
Headers:
  - Authorization: Bearer {API_KEY}
Body:
  - url: {target_url}
  - formats: ["markdown", "html"]
```

---

### 2.3 Module Content Comparator (`content_comparator.py`)

**Responsabilités :**
- Comparer deux versions de contenu (diff)
- Détecter les changements significatifs vs bruit
- Ignorer les éléments dynamiques (dates, compteurs)
- Calculer un score de similarité

**Algorithmes possibles :**
- **Diff textuel** : difflib (Python standard)
- **Similarité sémantique** : embeddings (OpenAI/sentence-transformers)
- **Détection structurelle** : BeautifulSoup pour HTML
- **Hash comparison** : pour détection rapide de changements

**Critères de changement significatif :**
- Seuil de différence (ex: >5% du contenu)
- Whitelist/blacklist de sélecteurs
- Exclusion d'éléments dynamiques (timestamps, cookies banners)

---

### 2.4 Module Sheets Manager (`sheets_manager.py`)

**Responsabilités :**
- Authentification OAuth2 Google
- Créer/mettre à jour les onglets "Log" et "Comparison"
- Stocker l'historique des scrapings
- Récupérer la version précédente pour comparaison

**Structure des données :**

**Log Sheet :**
| Timestamp | URL | Instruction | Content Hash | Status |
|-----------|-----|-------------|--------------|--------|
| 2025-11-05 10:00 | techcorp.com/pricing | surveille prix | abc123... | success |

**Comparison Sheet :**
| Date | URL | Changes Detected | Diff Summary | Notification Sent |
|------|-----|------------------|--------------|-------------------|
| 2025-11-05 10:00 | techcorp.com/pricing | Yes | Prix plan Pro: $99→$129 | Yes |

**API Google Sheets :**
- Utiliser `gspread` ou `google-api-python-client`
- OAuth2 avec service account ou user credentials
- Gestion des quotas (100 requêtes/100s par utilisateur)

---

### 2.5 Module Gmail Notifier (`gmail_notifier.py`)

**Responsabilités :**
- Authentification Gmail API
- Générer des emails HTML formatés
- Envoyer uniquement si changement détecté
- Inclure un résumé des modifications

**Template email :**
```
Sujet: [Monitor Agent] Changements détectés sur {site_name}

Corps:
🔔 Changements détectés le {timestamp}

📍 URL surveillée: {url}
📝 Instruction: {user_instruction}

🔍 Résumé des changements:
{diff_summary}

🔗 Voir les détails: {google_sheets_link}
```

**API Gmail :**
- Authentification OAuth2
- Quotas: 500 emails/jour (utilisateur standard)
- Format MIME pour emails HTML

---

## Phase 3 : Orchestration & Logique Métier

### 3.1 Workflow principal (`main.py`)

```
1. Recevoir instruction utilisateur
   ↓
2. AI Agent → Extraire URL + éléments cibles
   ↓
3. Firecrawl → Scraper le site (contenu actuel)
   ↓
4. Sheets Manager → Récupérer version précédente
   ↓
5. Content Comparator → Comparer les versions
   ↓
6. SI changement détecté:
   a. Sheets Manager → Logger le changement
   b. Gmail Notifier → Envoyer alerte
   ↓
7. SINON: Logger "aucun changement"
```

**Gestion des erreurs :**
- Chaque module doit avoir son propre error handling
- Logs détaillés à chaque étape
- Notifications d'erreurs critiques
- Continuation du workflow même si un composant échoue

---

### 3.2 Scheduling (exécution automatique)

**Options :**

1. **APScheduler (Python)** - Recommandé
   - Léger, intégré au code
   - Scheduling flexible (cron-like)
   - Persistence des jobs
   
   ```python
   from apscheduler.schedulers.blocking import BlockingScheduler
   
   scheduler = BlockingScheduler()
   scheduler.add_job(monitor_website, 'interval', hours=24)
   scheduler.start()
   ```

2. **Cron (Linux/Mac)** - Simple
   ```bash
   # Exécuter tous les jours à 10h
   0 10 * * * cd /path/to/project && python src/main.py
   ```

3. **Celery** - Pour tâches distribuées
   - Plus complexe, nécessite Redis/RabbitMQ
   - Idéal pour scaling

4. **n8n** - No-code (comme template)
   - Interface visuelle
   - Intégrations natives
   - Moins de contrôle programmatique

---

## Phase 4 : Points Critiques à Considérer

### 4.1 Sécurité

- ✅ Stocker les clés API dans `.env` (jamais dans le code)
- ✅ Utiliser OAuth2 pour Google (pas de mots de passe)
- ✅ Valider toutes les entrées utilisateur
- ✅ Rate limiting sur les APIs externes
- ✅ Chiffrement des données sensibles dans Sheets
- ✅ .gitignore pour `.env`, credentials, logs

### 4.2 Fiabilité

- ✅ Gérer les erreurs de chaque API (retry logic)
- ✅ Logs détaillés pour debug (utiliser `logging` module)
- ✅ Fallback si Firecrawl échoue (scraper basique avec BeautifulSoup?)
- ✅ Notifications d'erreurs critiques (email admin)
- ✅ Health checks réguliers
- ✅ Timeouts configurables

### 4.3 Performance

- ⚠️ Firecrawl peut être lent (10-30s par page)
- ⚠️ Limiter le nombre de sites surveillés simultanément
- ⚠️ Optimiser les comparaisons (hashs avant diff complet)
- ⚠️ Cache des résultats AI Agent (même instruction = même URL)
- ⚠️ Pagination pour historique Sheets (ne pas charger tout)

### 4.4 Coûts

| Service | Tarification | Limite gratuite | Coût estimé |
|---------|--------------|-----------------|-------------|
| Firecrawl | ~$0.001-0.01/scrape | Variable | $0.60-6/mois (2 scrapes/jour) |
| OpenAI API | ~$0.002/instruction | $5 crédit initial | $0.12/mois (2 instructions/jour) |
| Google Sheets | Gratuit | 10M cellules | $0 |
| Gmail API | Gratuit | 500 emails/jour | $0 |
| **Total** | | | **~$1-7/mois** |

### 4.5 Précision de détection

**Faux positifs à éviter :**
- Timestamps dynamiques
- Cookies banners
- Publicités rotatives
- Compteurs de visiteurs
- Numéros de sessions

**Stratégies :**
- Définir un seuil de changement (ex: >5% de différence)
- Whitelist de sélecteurs importants
- Blacklist d'éléments à ignorer
- Normalisation du contenu (strip whitespace, lowercase pour certains)

---

## Phase 5 : Amélioration Continue

### 5.1 Features avancées

- 📊 **Dashboard** : Visualiser l'historique des changements (Streamlit/Flask)
- 🔔 **Multi-canal** : Notifications Slack/Discord/Telegram en plus de Gmail
- 🤖 **AI Summarization** : Résumer les changements en langage naturel
- 📈 **Analyse de tendances** : Fréquence des changements, patterns
- 🔄 **Multi-sites parallèle** : Surveiller plusieurs sites simultanément
- 🎯 **Surveillance ciblée** : Sélecteurs CSS personnalisés
- 📱 **Interface web** : Pour gérer les surveillances
- 🧪 **Mode test** : Comparer deux URLs arbitraires
- 📦 **Export** : Télécharger historique en CSV/PDF

### 5.2 Tests

**Tests unitaires :**
- Chaque module testé indépendamment
- Mocking des APIs externes (responses library)
- Couverture de code >80%

**Tests d'intégration :**
- Workflow complet avec APIs mockées
- Validation du flux de données entre modules

**Tests end-to-end :**
- Utiliser des sites de démo/staging
- Vérifier les notifications réelles

**Outils recommandés :**
- `pytest` : Framework de tests
- `pytest-mock` : Mocking
- `responses` : Mock HTTP requests
- `coverage` : Couverture de code

---

## 🎯 Ordre de développement recommandé

### Sprint 1 : Setup (Semaine 1)
1. ✅ Créer structure de fichiers
2. ✅ Configurer `.gitignore`, `.env.example`
3. ✅ Définir `requirements.txt`
4. ✅ Setup config centralisée (`config/settings.py`)

### Sprint 2 : Core Scraping (Semaine 1-2)
5. ✅ Implémenter Firecrawl scraper
6. ✅ Tester extraction Markdown + HTML
7. ✅ Gérer erreurs et retry logic

### Sprint 3 : Storage (Semaine 2)
8. ✅ Implémenter Sheets Manager
9. ✅ CRUD basique sur Google Sheets
10. ✅ Créer templates Log + Comparison

### Sprint 4 : Comparison (Semaine 2-3)
11. ✅ Implémenter Content Comparator
12. ✅ Algo de diff simple (difflib)
13. ✅ Tester avec exemples réels

### Sprint 5 : Notifications (Semaine 3)
14. ✅ Implémenter Gmail Notifier
15. ✅ Template d'email HTML
16. ✅ Tester envoi notifications

### Sprint 6 : AI Agent (Semaine 3-4)
17. ✅ Implémenter AI Agent
18. ✅ Parser instructions naturelles
19. ✅ Valider extraction d'URLs

### Sprint 7 : Orchestration (Semaine 4)
20. ✅ Assembler tous les modules dans `main.py`
21. ✅ Workflow complet end-to-end
22. ✅ Gestion d'erreurs globale

### Sprint 8 : Automation (Semaine 4-5)
23. ✅ Implémenter scheduling (APScheduler)
24. ✅ Logs persistants
25. ✅ Tests avec surveillance réelle 24h

### Sprint 9 : Tests & Polish (Semaine 5)
26. ✅ Tests unitaires
27. ✅ Tests d'intégration
28. ✅ Documentation README

### Sprint 10 : Déploiement (Semaine 5-6)
29. ✅ Configurer serveur/cloud (AWS/GCP/Heroku)
30. ✅ Monitoring production
31. ✅ Setup alertes d'erreurs

---

## 📋 Checklist avant de coder

### Comptes & APIs
- [ ] Créer compte Firecrawl + obtenir API key
- [ ] Créer compte OpenAI/Claude + obtenir API key
- [ ] Configurer Google Cloud Project
- [ ] Activer Google Sheets API
- [ ] Activer Gmail API
- [ ] Créer OAuth2 credentials (service account)

### Décisions techniques
- [ ] Choisir AI provider (OpenAI vs Claude)
- [ ] Choisir stratégie scheduling (APScheduler vs Cron vs n8n)
- [ ] Définir seuil de changement significatif
- [ ] Décider format d'instructions utilisateur

### Préparation
- [ ] Préparer 3-5 sites de test pour validation
- [ ] Créer Google Sheet template (Log + Comparison)
- [ ] Définir structure des logs
- [ ] Préparer exemples d'instructions

---

## 🚀 Prochaines étapes immédiates

### Questions à clarifier :
1. **AI Provider** : OpenAI ou Claude pour l'agent IA ?
2. **Scheduling** : Python (APScheduler) ou externe (Cron/n8n) ?
3. **Comptes API** : Lesquels sont déjà configurés ?
4. **Use cases** : Quels sites voulez-vous surveiller en premier ?

### Actions recommandées :
1. Créer la structure de fichiers complète
2. Configurer `.env.example` avec toutes les variables
3. Générer `requirements.txt` détaillé
4. Commencer par le module Firecrawl (le plus critique)

---

## 📚 Ressources utiles

### Documentation APIs
- [Firecrawl API Docs](https://docs.firecrawl.dev)
- [OpenAI API Reference](https://platform.openai.com/docs)
- [Google Sheets API Python](https://developers.google.com/sheets/api/quickstart/python)
- [Gmail API Python](https://developers.google.com/gmail/api/quickstart/python)

### Libraries Python
- `firecrawl-py` : Client Python pour Firecrawl
- `openai` : Client OpenAI
- `anthropic` : Client Claude (Anthropic)
- `gspread` : Google Sheets wrapper
- `google-auth` : OAuth2 Google
- `apscheduler` : Job scheduling
- `python-dotenv` : Gestion .env
- `beautifulsoup4` : HTML parsing (fallback)
- `difflib` : Text comparison (stdlib)
- `pytest` : Testing framework

### Exemples de projets similaires
- [Website Monitor (GitHub)](https://github.com/topics/website-monitoring)
- [n8n Templates](https://n8n.io/workflows)

---

**Version:** 1.0  
**Date:** 5 novembre 2025  
**Statut:** Planning phase
