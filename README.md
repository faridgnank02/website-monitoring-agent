# Monitoring website agent

Intelligent web monitoring agent with automatic change detection and email notifications.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## Description

This project is an automated system that:

- Understands natural language instructions (e.g., "monitor prices on Zalando")
- Scrapes websites with JavaScript support (via Firecrawl)
- Detects and analyzes content changes using difflib
- Archives history in Google Sheets
- Sends HTML email notifications

### Usage Example

Give it a natural language instruction like:

> *"monitor prices on the Zalando men's page"*

And it will:
1. Automatically identify the correct URL (`https://www.zalando.fr/homme`)
2. Scrape the site (even JavaScript-heavy sites) - 56,509 characters extracted
3. Compare with the previous version (intelligent diff using difflib)
4. Store history in Google Sheets
5. Send an email alert if change > defined threshold (5.0% detected)

## Architecture

```
monitor_agent/
├── main.py                      # Main orchestrator
├── config/
│   ├── settings.py             # Centralized configuration
│   ├── sites.yaml              # List of sites to monitor
│   ├── .env                    # Environment variables (to create)
│   └── .env.example            # Configuration template
├── src/
│   ├── modules/
│   │   ├── ai_agent.py         # Instruction parsing (Groq LLM)
│   │   ├── firecrawl_scraper.py # Web scraping (Firecrawl API)
│   │   ├── content_comparator.py # Change detection
│   │   ├── sheets_manager.py   # Google Sheets management
│   │   └── gmail_notifier.py   # Email notifications
│   └── utils/
│       └── logger.py           # Logging system
└── tests/                      # Unit tests

```

## Prerequisites

- Python 3.9+
- Google Cloud account (for Sheets API)
- Gmail account with App Password
- API Keys: Groq, Firecrawl

## Installation

### 1. Clone the project

```bash
git clone <repository_url>
cd monitor_agent
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Google Sheets API Configuration

#### a) Create a Google Cloud project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Google Sheets API:
   - Menu: "APIs & Services" → "Enable APIs and Services"
   - Search "Google Sheets API" → Enable

#### b) Create a service account

1. Menu: "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Name the account (e.g., `monitor-agent`)
4. Create a JSON key:
   - Click on the created account
   - "Keys" tab → "Add Key" → "Create new key" → JSON
5. Download and save the file as `credentials.json` at the project root

#### c) Create and share a Google Sheet

1. Create a new [Google Sheet](https://sheets.google.com)
2. Copy the sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
   ```
3. Share the sheet with the service account email (from `credentials.json`)
   - Right-click → Share
   - Paste the service account email
   - Grant "Editor" permissions

### 5. Gmail App Password Configuration

#### a) Enable 2-step verification

1. Go to [Google Account](https://myaccount.google.com)
2. Security → 2-Step Verification → Enable

#### b) Generate an App Password

1. Security → 2-Step Verification → App passwords
2. Create a new password:
   - Application: "Mail"
   - Device: "Other" → "Monitor Agent"
3. Copy the generated password (16 characters)

### 6. Environment variables configuration

```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your values:

```env
# Groq API (LLM for instruction parsing)
GROQ_API_KEY=gsk_...

# Firecrawl API (Web scraping)
FIRECRAWL_API_KEY=fc-...

# Google Sheets
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=1DXPcaCriAUVmS7y2pWkEsfJ6MPtSM_ixv0AbZbjxjfs

# Gmail
GMAIL_SENDER_EMAIL=your-email@gmail.com
GMAIL_RECIPIENT_EMAIL=recipient@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 7. Sites to monitor configuration

Edit `config/sites.yaml`:

```yaml
sites:
  - instruction: "monitor prices on Zalando men's page"
    schedule: "daily 10:00"
    active: true
    threshold: 1.0
    tags:
      - pricing
      - ecommerce
    notes: "Men's fashion price monitoring"

  - instruction: "monitor TechCrunch blog for new AI articles"
    schedule: "twice-daily"
    active: false
    threshold: 5.0
    tags:
      - news
      - tech
```

**Parameters:**
- `instruction`: Natural language description (parsed by AI Agent)
- `schedule`: Frequency (for future automation)
- `active`: `true` to enable monitoring
- `threshold`: Change threshold (%) to trigger notification
- `tags`: Labels for categorization
- `notes`: Additional notes

## Usage

### Run monitoring

```bash
python3 main.py
```

**Workflow:**

1. Module initialization (Sheets, Gmail)
2. Loading `sites.yaml`
3. For each active site:
   - Parse instruction → URL
   - Scrape content
   - Calculate MD5 hash
   - Save to Google Sheets
   - Compare with previous version
   - Send email if change > threshold

### View logs

Logs are in Google Sheets with 2 tabs:

- **Log**: History of all scrapings
- **Comparison**: History of comparisons and detected changes

### Email notification format

HTML email with:

- Header with colored gradient
- Severity badge (Normal/Moderate/Important/Critical)
- Change statistics (added/removed/modified lines)
- Diff summary
- Link to monitored site
- Responsive design

## Tests

### Run all tests

```bash
# AI Agent tests
python3 tests/test_ai_agent.py

# Content Comparator tests
python3 tests/test_content_comparator.py

# Sheets Manager tests
python3 tests/test_sheets_manager.py

# Gmail Notifier tests
python3 tests/test_gmail_notifier.py
```

## Advanced Configuration

### Adjust detection sensitivity

In `sites.yaml`, modify the `threshold`:

- `0.1`: Very sensitive (minor changes)
- `1.0`: Normal sensitivity
- `5.0`: Low sensitivity (major changes only)

### Customize email templates

Templates are in `src/modules/gmail_notifier.py`:

- `_create_html_template()`: HTML email
- `_create_text_fallback()`: Text version

### Custom logger

Configuration in `src/utils/logger.py`:

```python
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
```

## Data Structure

### Google Sheets - "Log" Tab

| Timestamp | URL | Instruction | Status | Content Hash | Content Length | Error | Metadata |
|-----------|-----|-------------|--------|--------------|----------------|-------|----------|
| 2025-11-06T10:30:00 | https://... | monitor... | success | a1b2c3... | 56509 | | {...} |

### Google Sheets - "Comparison" Tab

| Timestamp | URL | Changes | Score % | Lines + | Lines - | Lines Δ | Threshold % | Summary |
|-----------|-----|---------|---------|---------|---------|---------|-------------|---------|
| 2025-11-06T10:30:00 | https://... | YES | 5.23% | 12 | 5 | 8 | 1.0% | Prices modified... |

## Contributing

Contributions are welcome! Some ideas:

- Automation with APScheduler
- Slack/Discord support
- Web dashboard
- Multi-recipient support
- PDF report export

## License

MIT License

## Troubleshooting

### Google authentication error

```text
google.auth.exceptions.DefaultCredentialsError
```

**Solution:** Verify that `credentials.json` exists and the path in `.env` is correct.

### Email not sent

```text
SMTPAuthenticationError: Username and Password not accepted
```

**Solution:**

1. Verify that 2-step verification is enabled
2. Regenerate an App Password
3. Verify that `GMAIL_APP_PASSWORD` in `.env` is correct (no spaces)

### Firecrawl timeout

```text
ERR_TIMED_OUT
```

**Solution:** The site may be inaccessible or blocking scrapers. Test with another site or verify the URL.

### Identical hash despite changes

**Solution:** Dynamic content (ads, clock) may vary. Increase the `threshold` or filter content before comparison.

## Support

For any questions or issues:

- Email: your-email@example.com
- Issues: [GitHub Issues](repository_url/issues)

---

**Made with passion**
