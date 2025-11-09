# Technical Documentation - Monitor Agent

## Overview

This project is an automated website monitoring system built around a modular architecture. The system uses 5 independent modules orchestrated by `main.py`.

## Global Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       scheduler.py                          │
│              (APScheduler - Automated Execution)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ triggers at scheduled times
                              │
┌─────────────────────────────▼───────────────────────────────┐
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

## Detailed Modules

### 1. AI Agent (244 lines)

**Role:** Parses natural language instructions and extracts URL + elements to monitor.

**Technologies:**
- Groq API (llama-3.1-8b-instant)
- JSON Schema validation

**Main function:**
```python
def parse_instruction(instruction: str) -> ParsedInstruction
```

**Input:**
```
"monitor prices on Zalando men's page"
```

**Output:**
```python
ParsedInstruction(
    url="https://www.zalando.fr/homme",
    elements_to_watch=["prices"],
    success=True
)
```

**Prompt Engineering:**
- System prompt with few-shot examples
- Strict JSON output format
- Pydantic validation

**Error handling:**
- Automatic retry (3 attempts)
- Fallback if JSON parsing fails
- Detailed logging

---

### 2. Firecrawl Scraper (202 lines)

**Role:** Scrapes web content with JavaScript support.

**Technologies:**
- Firecrawl API
- Retry logic with exponential backoff

**Main function:**
```python
def scrape_url(url: str, max_retries: int = 3) -> ScrapedContent
```

**Features:**
- JavaScript support (dynamic pages)
- Markdown + HTML extraction
- Metadata (title, description, language)
- Configurable timeout

**Output:**
```python
ScrapedContent(
    url="https://example.com",
    markdown="# Title\nContent...",
    html="<html>...</html>",
    metadata=DocumentMetadata(
        title="Page title",
        description="...",
        language="en"
    ),
    success=True
)
```

**Retry Strategy:**
1. Attempt 1: 30s timeout
2. Attempt 2: 60s timeout
3. Attempt 3: 90s timeout

---

### 3. Content Comparator (347 lines)

**Role:** Compares two content versions and detects changes.

**Technologies:**
- **difflib** (Python standard library) - Diff calculation and similarity
- Custom filtering algorithm for dynamic content
- Scoring based on number of modified lines

**Main function:**
```python
def compare_content(old_content: str, new_content: str) -> ComparisonResult
```

**Calculated metrics:**
- **change_score**: Change percentage (0-100%)
- **added_lines**: Number of added lines
- **removed_lines**: Number of removed lines
- **modified_lines**: Number of modified lines
- **similarity_ratio**: Similarity score (0-1) via `difflib.SequenceMatcher`

**difflib usage:**

1. **`difflib.unified_diff()`** - Generates unified format diff (like `git diff`)
   ```python
   diff = list(difflib.unified_diff(
       lines_old,
       lines_new,
       lineterm=''
   ))
   ```
   Used to generate a readable change summary.

2. **`difflib.SequenceMatcher()`** - Calculates similarity between two strings
   ```python
   ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
   # ratio = 0.85 means 85% similarity
   ```
   Used to detect modified lines (similar but not identical).

**Algorithm:**
```python
# 1. Normalization
old_normalized = normalize_text(old_content)
new_normalized = normalize_text(new_content)

# 2. Dynamic content filtering (timestamps, sessions, etc.)
old_filtered = filter_dynamic_content(old_normalized)
new_filtered = filter_dynamic_content(new_normalized)

# 3. Change detection
added = [line for line in new_filtered if line not in old_filtered]
removed = [line for line in old_filtered if line not in new_filtered]

# 4. Modification detection (difflib.SequenceMatcher)
modified = []
for old_line in removed:
    for new_line in added:
        if difflib.SequenceMatcher(None, old_line, new_line).ratio() >= 0.7:
            modified.append((old_line, new_line))

# 5. Score calculation
change_score = (len(added) + len(removed) + len(modified)) / total_lines * 100
```

**Normalization:**
- Multiple space removal
- Lowercase (optional)
- Empty line removal

**Dynamic filtering:**
Ignores patterns that change frequently:
- Dates (`2025-11-06`, `06/11/2025`)
- Times (`10:30:45`)
- Timestamps (`Updated: ...`, `Last modified: ...`)
- Session IDs
- Visitor counters
- Copyrights with years

---

### 4. Sheets Manager (606 lines)

**Role:** History management in Google Sheets.

**Technologies:**
- Google Sheets API v4
- Service Account authentication
- Batch operations

**Main classes:**

#### ScrapingLog
```python
@dataclass
class ScrapingLog:
    timestamp: str
    url: str
    instruction: str
    status: str  # "success" or "error"
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

**Main methods:**
- `authenticate()`: Service account authentication
- `initialize_sheets()`: Create Log/Comparison tabs
- `log_scraping(log)`: Record a scraping
- `log_comparison(log)`: Record a comparison
- `get_last_scraping(url)`: Retrieve last scraping
- `get_scraping_history(url, limit)`: Complete history

**Optimizations:**
- Batch writes (append instead of insert)
- Existing tab cache
- Automatic formatting (bold headers, gray background)

---

### 5. Gmail Notifier (412 lines)

**Role:** HTML email notifications.

**Technologies:**
- SMTP (Gmail)
- HTML/CSS (email templates)
- TLS encryption

**HTML Template (6208 characters):**

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    /* Responsive email styles */
  </style>
</head>
<body>
  <div class="container">
    <!-- Notification content -->
  </div>
</body>
</html>
```

**Severity levels:**
- **Normal** (< 5%): Blue badge
- **Moderate** (5-15%): Orange badge
- **Important** (15-30%): Red badge
- **Critical** (> 30%): Dark red badge

**Text fallback (702 characters):**
Text version for email clients without HTML support.

**Security:**
- App Password (not main password)
- TLS encryption
- Parameter validation

---

### 6. Scheduler (180 lines)

**Role:** Automated cron-based scheduling for monitoring tasks.

**Technologies:**
- APScheduler 3.10.4
- BlockingScheduler (continuous execution)
- CronTrigger (time-based scheduling)

**Main functions:**

#### parse_schedule
```python
def parse_schedule(schedule_str: str) -> dict
```

Converts YAML schedule strings to cron parameters.

**Supported formats:**
- `"daily 10:00"` → `{'hour': 10, 'minute': 0}`
- `"twice-daily"` → Two jobs at 9:00 and 18:00
- `"hourly"` → `{'minute': 0}`
- `"every X hours"` → `{'hour': '*/X'}`
- `"monday 14:30"` → `{'day_of_week': 'mon', 'hour': 14, 'minute': 30}`

**Input (sites.yaml):**
```yaml
sites:
  - name: "Zalando Men Prices"
    instruction: "monitor prices on Zalando men's page"
    schedule: "daily 10:00"
    active: true
    threshold: 1.0
```

**Output:**
```python
{
    'hour': 10,
    'minute': 0
}
```

#### run_monitoring_for_site
```python
def run_monitoring_for_site(site_config: dict)
```

Wrapper that executes monitoring for a specific site configuration.

**Workflow:**
1. Initialize MonitorAgent
2. Call `monitor_site(site_config)`
3. Log execution results
4. Handle errors gracefully

#### setup_scheduler
```python
def setup_scheduler() -> BlockingScheduler
```

Configures APScheduler with all active sites from `sites.yaml`.

**Process:**
1. Load sites configuration
2. Filter active sites (`active: true`)
3. Parse schedule for each site
4. Create CronTrigger jobs
5. Return configured scheduler

**Example output:**
```
INFO:src.scheduler:Scheduled: 'monitor Zalando prices' with {'hour': 10, 'minute': 0}
INFO:src.scheduler:Total jobs scheduled: 1
INFO:src.scheduler:Next run times:
  - monitor Zalando prices: 2025-11-10 10:00:00
```

#### main
```python
def main()
```

Entry point that starts the scheduler.

**Execution:**
```bash
# Run in foreground
python3 src/scheduler.py

# Run in background (macOS/Linux)
nohup python3 src/scheduler.py &

# Stop background process
pkill -f "python3 src/scheduler.py"
```

**Production deployment options:**
- **systemd** (Linux) - Auto-restart on boot
- **launchd** (macOS) - Launch agent
- **Docker** - Containerized deployment
- **Cloud VM** - Railway.app, Render.com, DigitalOcean

See `SCHEDULING.md` for complete deployment guide.

---

## Complete Workflow

### Manual Execution

### 1. Initialization
```python
agent = MonitorAgent()
# - Initialize SheetsManager
# - Initialize GmailNotifier
# - Authenticate Google Sheets API
# - Check Log/Comparison tabs
```

### 2. Configuration Loading
```python
sites = agent.load_sites_config()
# - Parse sites.yaml
# - Filter active sites (active: true)
# - Return list of configs
```

### 3. Monitoring (per site)
```python
for site in sites:
    agent.monitor_site(site)
```

**Detailed steps:**

#### 3.1 Instruction Parsing
```python
parsed = parse_instruction(instruction)
# Input: "monitor Zalando prices"
# Output: url="https://www.zalando.fr", elements=["prices"]
```

#### 3.2 Scraping
```python
scraped = scrape_url(url)
# - Call Firecrawl API
# - Extract markdown + HTML
# - Retrieve metadata
```

#### 3.3 Hash Calculation
```python
content_hash = hashlib.md5(scraped.markdown.encode('utf-8')).hexdigest()
# MD5 hash for quick comparison
```

#### 3.4 Scraping Logging
```python
sheets_manager.log_scraping(ScrapingLog(...))
# Record in "Log" tab
```

#### 3.5 History Retrieval
```python
history = sheets_manager.get_scraping_history(url, limit=2)
previous = history[1]  # Second-to-last (last = just created)
```

#### 3.6 Comparison
```python
if content_hash == previous_hash:
    # No changes
    change_score = 0.0
else:
    # Changes detected
    comparison = compare_content(previous_content, current_content)
    change_score = comparison.change_score
```

#### 3.7 Comparison Logging
```python
sheets_manager.log_comparison(ComparisonLog(...))
# Record in "Comparison" tab
```

#### 3.8 Notification (if change > threshold)
```python
if change_score > threshold:
    notification = ChangeNotification(...)
    gmail_notifier.send_notification(notification)
```

### 4. Summary
```python
# Display final statistics
logger.info(f"Sites monitored: {total}")
logger.info(f"Success: {success}")
logger.info(f"Errors: {errors}")
```

### Automated Execution (Scheduler)

### 1. Scheduler Initialization
```python
scheduler = setup_scheduler()
# - Load sites.yaml
# - Parse schedules for each site
# - Create CronTrigger jobs
# - Return configured BlockingScheduler
```

### 2. Job Scheduling
```python
for site in active_sites:
    schedule = parse_schedule(site['schedule'])
    scheduler.add_job(
        run_monitoring_for_site,
        trigger=CronTrigger(**schedule),
        args=[site],
        id=site['name']
    )
```

### 3. Continuous Execution
```python
scheduler.start()
# BlockingScheduler runs forever
# Executes jobs at scheduled times
# Uses main.MonitorAgent for each job
```

### 4. Scheduled Monitoring
At each scheduled time:
```python
run_monitoring_for_site(site_config)
# - Initialize MonitorAgent
# - Call monitor_site(site_config)
# - Same workflow as manual execution (sections 1-4 above)
# - Log results
```

**Example logs:**
```
INFO:src.scheduler:Scheduled: 'monitor Zalando prices' with {'hour': 10, 'minute': 0}
INFO:src.scheduler:Total jobs scheduled: 1
INFO:apscheduler.scheduler:Scheduler started
INFO:apscheduler.executors.default:Running job "monitor Zalando prices" (scheduled at 2025-11-10 10:00:00)
```

---

## Deployment Options

### Local Machine
**Advantages:**
- No cost
- Quick setup

**Disadvantages:**
- Must stay powered on 24/7
- Not accessible remotely

**Setup (macOS with launchd):**
```bash
# Create ~/Library/LaunchAgents/com.monitoragent.plist
launchctl load ~/Library/LaunchAgents/com.monitoragent.plist
```

### Cloud VM (Recommended)
**Providers:**
- Railway.app (5$/month)
- Render.com (free tier available)
- DigitalOcean (6$/month)
- Fly.io (free tier 256MB)

**Advantages:**
- Always available
- Accessible anywhere
- Easy scaling

**Setup:**
```bash
# Deploy via Git
git push railway main

# Or use systemd on Linux VM
sudo systemctl enable monitor-agent
sudo systemctl start monitor-agent
```

See `SCHEDULING.md` for complete deployment instructions.

---

## Summary
```

---

## Configuration

### Environment variables (.env)

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
  - instruction: "monitor Zalando prices"
    schedule: "daily 10:00"
    active: true
    threshold: 1.0
    tags:
      - pricing
      - ecommerce
    notes: "Price monitoring"
```

**Parameters:**
- `instruction`: Natural language (parsed by AI Agent)
- `schedule`: For future automation
- `active`: On/off activation
- `threshold`: Change threshold (%)
- `tags`: Categorization
- `notes`: Documentation

---

## Data Structures

### Google Sheets - "Log" Tab

| Column | Type | Description |
|---------|------|-------------|
| Timestamp | ISO 8601 | Scraping date/time |
| URL | String | Scraped URL |
| Instruction | String | Original instruction |
| Status | Enum | success/error |
| Content Hash | MD5 | Content hash |
| Content Length | Integer | Size in characters |
| Error | String | Error message (if failed) |
| Metadata | JSON | Additional metadata |

### Google Sheets - "Comparison" Tab

| Column | Type | Description |
|---------|------|-------------|
| Timestamp | ISO 8601 | Comparison date/time |
| URL | String | Compared URL |
| Instruction | String | Original instruction |
| Changes | Boolean | YES/NO |
| Score % | Float | Change score |
| Lines + | Integer | Added lines |
| Lines - | Integer | Removed lines |
| Lines Δ | Integer | Modified lines |
| Threshold % | Float | Configured threshold |
| Summary | String | Text summary |
| Old Hash | MD5 | Previous version hash |
| New Hash | MD5 | Current version hash |

---

## Error Management

### Management levels

**1. Module-level:**
Each module handles its own errors:
- Retry with backoff (Firecrawl)
- JSON parsing fallback (AI Agent)
- Connection retry (Sheets, Gmail)

**2. Orchestrator-level:**
`main.py` captures exceptions:
```python
try:
    agent.monitor_site(site)
    success_count += 1
except Exception as e:
    logger.error(f"Error: {e}")
    error_count += 1
    continue  # Continue with next site
```

**3. Logging:**
All modules use centralized logger:
- **INFO**: Normal operations
- **WARNING**: Changes detected, non-critical situations
- **ERROR**: Failures, exceptions

### Recovery strategies

**Firecrawl timeout:**
1. Retry with increased timeout
2. If 3 failures → Log error in Sheets
3. Continue with next site

**Sheets API error:**
1. Retry authentication
2. If failure → Skip logging (continue workflow)
3. Notification sent anyway

**Gmail SMTP error:**
1. Log error
2. Continue (notification failed but workflow OK)

---

## Performance

### Typical execution times

| Operation | Average time | Notes |
|-----------|-------------|-----------|
| Parse instruction | 1-2s | Groq API call |
| Scraping | 2-5s | Depends on site |
| Hash calculation | < 0.1s | MD5 very fast |
| Sheets write | 0.5-1s | Batch operation |
| Sheets read | 0.5-1s | Range query |
| Email send | 1-2s | SMTP connection |
| **Total per site** | **5-12s** | Variable |

### Possible optimizations

1. **Parallelization:**
   ```python
   from concurrent.futures import ThreadPoolExecutor
   
   with ThreadPoolExecutor(max_workers=3) as executor:
       executor.map(agent.monitor_site, sites)
   ```

2. **Caching:**
   ```python
   @lru_cache(maxsize=128)
   def parse_instruction(instruction: str):
       # Avoid re-parsing same instruction
   ```

3. **Batch Sheets operations:**
   ```python
   # Write multiple logs at once
   sheets.batch_update(...)
   ```

---

## Security

### Credentials Management

**Google Service Account:**
- Local JSON key (never committed)
- `.gitignore` includes `credentials.json`
- Minimal permissions (Sheets API only)

**Gmail App Password:**
- Main password not stored
- Individually revocable App Password
- `.env` in `.gitignore`

**API Keys:**
- Environment variables
- Never hardcoded
- Recommended rotation (90 days)

### Communication

**TLS/SSL:**
- Gmail SMTP: TLS encryption (port 587)
- Firecrawl API: HTTPS
- Google Sheets API: HTTPS

---

## Tests

### Unit Tests

**Files:**
- `tests/test_ai_agent.py`
- `tests/test_content_comparator.py`
- `tests/test_sheets_manager.py`
- `tests/test_gmail_notifier.py`

**Execution:**
```bash
python3 tests/test_ai_agent.py
```

**Coverage:**
- AI Agent: 100% (4/4 functions)
- Comparator: 100% (5/5 functions)
- Sheets Manager: 90% (8/9 methods)
- Gmail Notifier: 95% (simulation mode)

---

## Future Extensions

### 1. Automation (Priority: High)

**APScheduler:**
```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
scheduler.add_job(agent.run, 'cron', hour=10)  # Every day at 10am
scheduler.start()
```

**Systemd Service (Linux):**
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

### 2. Advanced Comparison

**Store complete content:**
```python
# Instead of just hash
sheets_manager.log_scraping_with_content(
    log=scraping_log,
    content=scraped.markdown  # Store in separate column
)
```

**Visual diff:**
```python
# Generate HTML diff
from difflib import HtmlDiff
differ = HtmlDiff()
html_diff = differ.make_file(old_lines, new_lines)
```

### 3. Multi-channel Notifications

**Slack:**
```python
from slack_sdk import WebClient

client = WebClient(token=SLACK_TOKEN)
client.chat_postMessage(
    channel="#monitoring",
    text=f"Change detected on {url}"
)
```

**Discord:**
```python
from discord_webhook import DiscordWebhook

webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)
webhook.set_content(content=notification_text)
webhook.execute()
```

### 4. Web Dashboard

**Streamlit:**
```python
import streamlit as st

st.title("Monitor Agent Dashboard")
st.line_chart(change_history)
```

---

## Performance Monitoring

### Key metrics to track:

- Scraping success rate
- Average response time per site
- API quota usage (Firecrawl, Groq)
- Error frequency
- Change detection accuracy

### Recommended tools:

- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **Sentry**: Error tracking
- **New Relic**: Application monitoring

---

## Best Practices

### Development

1. Always test with real websites
2. Handle rate limits gracefully
3. Log everything (INFO, WARNING, ERROR)
4. Write unit tests for new features
5. Document all configuration options

### Production

1. Use environment-specific configs
2. Monitor API quotas
3. Set up alerts for failures
4. Regular backup of Google Sheets
5. Rotate API keys periodically

### Maintenance

1. Review logs weekly
2. Update dependencies monthly
3. Test with new site structures
4. Archive old comparison data
5. Optimize slow operations

---

## Conclusion

This project provides a robust, modular, and extensible solution for automated website monitoring. The architecture allows for easy addition of new modules, alternative APIs, and custom notification channels.

The use of difflib for intelligent content comparison, combined with Google Sheets for persistent storage and Gmail for notifications, creates a complete monitoring pipeline that is both powerful and easy to maintain.
