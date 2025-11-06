# 📐 Documentation Technique - Monitor Agent

## Vue d'ensemble

Monitor Agent est un système de surveillance automatisé de sites web conçu autour d'une architecture modulaire. Le système utilise 5 modules indépendants orchestrés par `main.py`.


## Architecture Globale

```
┌─────────────────────────────────────────────────────────────┐
│                          main.py                            │
│                   (MonitorAgent Orchestrator)                │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
        ┌───────▼──────┐ ┌───▼────┐ ┌─────▼──────┐
        │  AI Agent    │ │ Scraper│ │ Comparator │
        │   (Groq)     │ │(Firecrawl)│ (difflib) │
        └──────────────┘ └────────┘ └────────────┘
                │             │             │
                └─────────────┼─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │                           │
          ┌─────▼──────┐           ┌──────▼─────┐
          │   Sheets   │           │   Gmail    │
          │  Manager   │           │  Notifier  │
          └────────────┘           └────────────┘
```

## Modules Détaillés

### 1. AI Agent (244 lignes)

**Rôle :** Parse les instructions en langage naturel et extrait l'URL + éléments à surveiller.

**Technologies :**
- Groq API (llama-3.1-8b-instant)
- JSON Schema validation

**Fonction principale :**
```python
def parse_instruction(instruction: str) -> ParsedInstruction
```

**Input :**
```
"surveille les prix sur la page homme de Zalando"
```

**Output :**
```python
ParsedInstruction(
    url="https://www.zalando.fr/homme",
    elements_to_watch=["prix"],
    success=True
)
```

**Prompt Engineering :**
- System prompt avec exemples few-shot
- Output format JSON strict
- Validation avec Pydantic

**Gestion d'erreurs :**
- Retry automatique (3 tentatives)
- Fallback si parsing JSON échoue
- Logging détaillé

---

### 2. Firecrawl Scraper (202 lignes)

**Rôle :** Scrape le contenu web avec support JavaScript.

**Technologies :**
- Firecrawl API
- Retry logic avec exponential backoff

**Fonction principale :**
```python
def scrape_url(url: str, max_retries: int = 3) -> ScrapedContent
```

**Features :**
- Support JavaScript (pages dynamiques)
- Extraction markdown + HTML
- Métadonnées (titre, description, langue)
- Timeout configurable

**Output :**
```python
ScrapedContent(
    url="https://example.com",
    markdown="# Title\nContent...",
    html="<html>...</html>",
    metadata=DocumentMetadata(
        title="Page title",
        description="...",
        language="fr"
    ),
    success=True
)
```

**Retry Strategy :**
1. Tentative 1 : timeout 30s
2. Tentative 2 : timeout 60s
3. Tentative 3 : timeout 90s

---

### 3. Content Comparator (347 lignes)

**Rôle :** Compare deux versions de contenu et détecte les changements.

**Technologies :**
- **difflib** (Python standard library) - Calcul de différences et similarité
- Algorithme de filtrage personnalisé pour contenu dynamique
- Scoring basé sur le nombre de lignes modifiées

**Fonction principale :**
```python
def compare_content(old_content: str, new_content: str) -> ComparisonResult
```

**Métriques calculées :**
- **change_score** : % de changement (0-100%)
- **added_lines** : Nombre de lignes ajoutées
- **removed_lines** : Nombre de lignes supprimées
- **modified_lines** : Nombre de lignes modifiées
- **similarity_ratio** : Score de similarité (0-1) via `difflib.SequenceMatcher`

**Utilisation de difflib :**

1. **`difflib.unified_diff()`** - Génère un diff au format unified (comme `git diff`)
   ```python
   diff = list(difflib.unified_diff(
       lines_old,
       lines_new,
       lineterm=''
   ))
   ```
   Utilisé pour générer un résumé lisible des changements.

2. **`difflib.SequenceMatcher()`** - Calcule la similarité entre deux chaînes
   ```python
   ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
   # ratio = 0.85 signifie 85% de similarité
   ```
   Utilisé pour détecter les lignes modifiées (similaires mais pas identiques).

**Algorithme :**
```python
# 1. Normalisation
old_normalized = normalize_text(old_content)
new_normalized = normalize_text(new_content)

# 2. Filtrage contenu dynamique (timestamps, sessions, etc.)
old_filtered = filter_dynamic_content(old_normalized)
new_filtered = filter_dynamic_content(new_normalized)

# 3. Détection changements
added = [line for line in new_filtered if line not in old_filtered]
removed = [line for line in old_filtered if line not in new_filtered]

# 4. Détection modifications (difflib.SequenceMatcher)
modified = []
for old_line in removed:
    for new_line in added:
        if difflib.SequenceMatcher(None, old_line, new_line).ratio() >= 0.7:
            modified.append((old_line, new_line))

# 5. Calcul du score
change_score = (len(added) + len(removed) + len(modified)) / total_lines * 100
```

**Normalisation :**
- Suppression espaces multiples
- Lowercase (optionnel)
- Suppression lignes vides

**Filtrage dynamique :**
Ignore les patterns qui changent fréquemment :
- Dates (`2025-11-06`, `06/11/2025`)
- Heures (`10:30:45`)
- Timestamps (`Updated: ...`, `Last modified: ...`)
- Session IDs
- Compteurs de visiteurs
- Copyright avec années

---

### 4. Sheets Manager (606 lignes)

**Rôle :** Gestion de l'historique dans Google Sheets.

**Technologies :**
- Google Sheets API v4
- Service Account authentication
- Batch operations

**Classes principales :**

#### ScrapingLog
```python
@dataclass
class ScrapingLog:
    timestamp: str
    url: str
    instruction: str
    status: str  # "success" ou "error"
    content_hash: str
    content_length: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

#### ComparisonLog
```python
@dataclass
class ComparisonLog:
    timestamp: str
    url: str
    instruction: str
    has_changes: bool
    change_score: float
    added_lines: int
    removed_lines: int
    modified_lines: int
    threshold: float
    diff_summary: str
    old_hash: str
    new_hash: str
```

**Méthodes principales :**
- `authenticate()` : Authentification service account
- `initialize_sheets()` : Création onglets Log/Comparison
- `log_scraping(log)` : Enregistrer un scraping
- `log_comparison(log)` : Enregistrer une comparaison
- `get_last_scraping(url)` : Récupérer dernier scraping
- `get_scraping_history(url, limit)` : Historique complet

**Optimisations :**
- Batch writes (append au lieu d'insert)
- Cache des onglets existants
- Formatting automatique (headers en gras, background gris)

---

### 5. Gmail Notifier (412 lignes)

**Rôle :** Envoi de notifications email HTML.

**Technologies :**
- SMTP (Gmail)
- HTML/CSS (email templates)
- TLS encryption

**Template HTML (6208 caractères) :**

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    /* Responsive design */
    /* Gradient header */
    /* Badge coloré (Normal/Modéré/Important/Critique) */
    /* Progress bars */
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🚨 Changement Détecté</h1>
    </div>
    
    <div class="badge severity-[level]">
      [Niveau de sévérité]
    </div>
    
    <div class="stats">
      <!-- Statistiques des changements -->
    </div>
    
    <div class="diff-summary">
      <!-- Résumé du diff -->
    </div>
    
    <div class="footer">
      <!-- Liens et timestamp -->
    </div>
  </div>
</body>
</html>
```

**Niveaux de sévérité :**
- **Normal** (< 5%) : Badge bleu
- **Modéré** (5-15%) : Badge orange
- **Important** (15-30%) : Badge rouge
- **Critique** (> 30%) : Badge rouge foncé

**Fallback texte (702 caractères) :**
Version texte pour clients email sans support HTML.

**Sécurité :**
- App Password (pas de mot de passe principal)
- TLS encryption
- Validation des paramètres

---

## Workflow Complet

### 1. Initialisation
```python
agent = MonitorAgent()
# - Initialise SheetsManager
# - Initialise GmailNotifier
# - Authentifie Google Sheets API
# - Vérifie onglets Log/Comparison
```

### 2. Chargement Configuration
```python
sites = agent.load_sites_config()
# - Parse sites.yaml
# - Filtre sites actifs (active: true)
# - Retourne liste de configs
```

### 3. Surveillance (par site)
```python
for site in sites:
    agent.monitor_site(site)
```

**Étapes détaillées :**

#### 3.1 Parsing Instruction
```python
parsed = parse_instruction(instruction)
# Input: "surveille les prix Zalando"
# Output: url="https://www.zalando.fr", elements=["prix"]
```

#### 3.2 Scraping
```python
scraped = scrape_url(url)
# - Appel Firecrawl API
# - Extraction markdown + HTML
# - Récupération métadonnées
```

#### 3.3 Hash Calculation
```python
content_hash = hashlib.md5(scraped.markdown.encode('utf-8')).hexdigest()
# Hash MD5 pour comparaison rapide
```

#### 3.4 Logging Scraping
```python
sheets_manager.log_scraping(ScrapingLog(...))
# Enregistre dans onglet "Log"
```

#### 3.5 Récupération Historique
```python
history = sheets_manager.get_scraping_history(url, limit=2)
previous = history[1]  # Avant-dernier (dernier = celui qu'on vient de créer)
```

#### 3.6 Comparaison
```python
if content_hash == previous_hash:
    # Aucun changement
    change_score = 0.0
else:
    # Changements détectés
    comparison = compare_content(old_content, new_content)
    change_score = comparison.change_score
```

#### 3.7 Logging Comparaison
```python
sheets_manager.log_comparison(ComparisonLog(...))
# Enregistre dans onglet "Comparison"
```

#### 3.8 Notification (si changement > seuil)
```python
if change_score > threshold:
    notification = ChangeNotification(...)
    gmail_notifier.send_notification(notification)
```

### 4. Résumé
```python
# Affiche statistiques finales
logger.info(f"Sites surveillés: {total}")
logger.info(f"✅ Succès: {success}")
logger.info(f"❌ Erreurs: {errors}")
```

---

## Configuration

### Variables d'environnement (.env)

```bash
# Groq API
GROQ_API_KEY=gsk_...

# Firecrawl API
FIRECRAWL_API_KEY=fc-...

# Google Sheets
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=1DXPcaC...
GOOGLE_SHEET_LOG_TAB=Log
GOOGLE_SHEET_COMPARISON_TAB=Comparison

# Gmail
GMAIL_SENDER_EMAIL=sender@gmail.com
GMAIL_RECIPIENT_EMAIL=recipient@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_SMTP_SERVER=smtp.gmail.com
GMAIL_SMTP_PORT=587
```

### Sites Configuration (sites.yaml)

```yaml
sites:
  - instruction: "surveille les prix Zalando"
    schedule: "daily 10:00"
    active: true
    threshold: 1.0
    tags:
      - pricing
      - ecommerce
    notes: "Surveillance quotidienne"
```

**Paramètres :**
- `instruction` : Langage naturel (parsé par AI Agent)
- `schedule` : Pour future automatisation
- `active` : Activation on/off
- `threshold` : Seuil de changement (%)
- `tags` : Catégorisation
- `notes` : Documentation

---

## Structures de Données

### Google Sheets - Onglet "Log"

| Colonne | Type | Description |
|---------|------|-------------|
| Timestamp | ISO 8601 | Date/heure du scraping |
| URL | String | URL scrapée |
| Instruction | String | Instruction originale |
| Status | Enum | success/error |
| Content Hash | MD5 | Hash du contenu |
| Content Length | Integer | Taille en caractères |
| Error | String | Message d'erreur (si échec) |
| Metadata | JSON | Métadonnées additionnelles |

### Google Sheets - Onglet "Comparison"

| Colonne | Type | Description |
|---------|------|-------------|
| Timestamp | ISO 8601 | Date/heure de la comparaison |
| URL | String | URL comparée |
| Instruction | String | Instruction originale |
| Changements | Boolean | OUI/NON |
| Score % | Float | Score de changement |
| Lignes + | Integer | Lignes ajoutées |
| Lignes - | Integer | Lignes supprimées |
| Lignes Δ | Integer | Lignes modifiées |
| Seuil % | Float | Seuil configuré |
| Résumé | String | Résumé textuel |
| Hash Ancien | MD5 | Hash version précédente |
| Hash Nouveau | MD5 | Hash version actuelle |

---

## Gestion des Erreurs

### Niveaux de gestion

**1. Module-level :**
Chaque module gère ses propres erreurs :
- Retry avec backoff (Firecrawl)
- Fallback JSON parsing (AI Agent)
- Connection retry (Sheets, Gmail)

**2. Orchestrator-level :**
`main.py` capture les exceptions :
```python
try:
    agent.monitor_site(site)
    success_count += 1
except Exception as e:
    logger.error(f"Erreur: {e}")
    error_count += 1
    continue  # Continue avec site suivant
```

**3. Logging :**
Tous les modules utilisent le logger centralisé :
- **INFO** : Opérations normales
- **WARNING** : Changements détectés, situations non-critiques
- **ERROR** : Échecs, exceptions

### Stratégies de recovery

**Firecrawl timeout :**
1. Retry avec timeout augmenté
2. Si 3 échecs → Log error dans Sheets
3. Continue avec site suivant

**Sheets API error :**
1. Retry authentification
2. Si échec → Skip logging (continue workflow)
3. Notification envoyée quand même

**Gmail SMTP error :**
1. Log error
2. Continue (notification échouée mais workflow OK)

---

## Performance

### Temps d'exécution typiques

| Opération | Temps moyen | Remarques |
|-----------|-------------|-----------|
| Parse instruction | 1-2s | Appel Groq API |
| Scraping | 2-5s | Dépend du site |
| Hash calculation | < 0.1s | MD5 très rapide |
| Sheets write | 0.5-1s | Batch operation |
| Sheets read | 0.5-1s | Range query |
| Email send | 1-2s | SMTP connection |
| **Total par site** | **5-12s** | Variable |

### Optimisations possibles

1. **Parallélisation :**
   ```python
   # Surveiller plusieurs sites en parallèle
   with ThreadPoolExecutor(max_workers=3) as executor:
       futures = [executor.submit(agent.monitor_site, site) 
                  for site in sites]
   ```

2. **Caching :**
   ```python
   # Cache des résultats AI Agent (même instruction)
   @lru_cache(maxsize=100)
   def parse_instruction_cached(instruction: str):
       return parse_instruction(instruction)
   ```

3. **Batch Sheets operations :**
   ```python
   # Écrire plusieurs logs en une seule requête
   sheets_manager.batch_log_scrapings(logs_list)
   ```

---

## Sécurité

### Credentials Management

**Google Service Account :**
- Clé JSON en local (jamais commité)
- `.gitignore` inclut `credentials.json`
- Permissions minimales (Sheets API uniquement)

**Gmail App Password :**
- Pas de mot de passe principal stocké
- App Password révocable individuellement
- `.env` dans `.gitignore`

**API Keys :**
- Variables d'environnement
- Jamais hardcodés
- Rotation recommandée (90 jours)

### Communication

**TLS/SSL :**
- Gmail SMTP : TLS encryption (port 587)
- Firecrawl API : HTTPS
- Google Sheets API : HTTPS

---

## Tests

### Tests Unitaires

**Fichiers :**
- `tests/test_ai_agent.py`
- `tests/test_content_comparator.py`
- `tests/test_sheets_manager.py`
- `tests/test_gmail_notifier.py`

**Exécution :**
```bash
python3 tests/test_ai_agent.py
```

**Coverage :**
- AI Agent : 100% (4/4 fonctions)
- Comparator : 100% (5/5 fonctions)
- Sheets Manager : 90% (8/9 méthodes)
- Gmail Notifier : 95% (simulation mode)

---

## Extensions Futures

### 1. Automatisation (Priorité: Haute)

**APScheduler :**
```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
scheduler.add_job(agent.run, 'cron', hour=10)  # Tous les jours à 10h
scheduler.start()
```

**Systemd Service (Linux) :**
```ini
[Unit]
Description=Monitor Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/monitor_agent
ExecStart=/home/ubuntu/monitor_agent/venv/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. Comparaison Avancée

**Stocker contenu complet :**
```python
# Au lieu de juste le hash
sheets_manager.log_scraping_with_content(
    log=scraping_log,
    content=scraped.markdown  # Stocker dans colonne séparée
)
```

**Diff visuel :**
```python
# Générer HTML diff
from difflib import HtmlDiff
differ = HtmlDiff()
html_diff = differ.make_file(old_lines, new_lines)
```

### 3. Multi-canal Notifications

**Slack :**
```python
from slack_sdk import WebClient

client = WebClient(token=SLACK_TOKEN)
client.chat_postMessage(
    channel="#monitoring",
    text=f"Changement détecté sur {url}"
)
```

**Discord :**
```python
from discord_webhook import DiscordWebhook

webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)
webhook.set_content(content=notification_text)
webhook.execute()
```

### 4. Dashboard Web

**Flask + Plotly :**
```python
@app.route('/dashboard')
def dashboard():
    history = sheets_manager.get_all_comparisons()
    fig = px.line(history, x='timestamp', y='change_score')
    return render_template('dashboard.html', graph=fig)
```

---

## Troubleshooting

### Debug Mode

Activer logs DEBUG :
```python
# src/utils/logger.py
LOG_LEVEL = "DEBUG"
```

### Problèmes courants

**1. Hash toujours différent :**
- Contenu dynamique (pub, horloge)
- **Solution :** Augmenter threshold ou filtrer contenu

**2. Firecrawl timeout :**
- Site lent ou bloquant scrapers
- **Solution :** Whitelist IP Firecrawl ou utiliser proxy

**3. Gmail authentication error :**
- App Password invalide
- **Solution :** Régénérer App Password

**4. Sheets API quota exceeded :**
- Trop de requêtes
- **Solution :** Batch operations ou cache

---

## Métriques de Qualité

### Code Quality

```bash
# Linting
pylint src/ main.py

# Type checking
mypy src/ main.py

# Code complexity
radon cc src/ -a
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

agent.run()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(10)
```

---

**Dernière mise à jour :** 6 novembre 2025  
