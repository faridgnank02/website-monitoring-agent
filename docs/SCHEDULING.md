# Scheduling Documentation - Monitor Agent

This guide explains how to automate Monitor Agent using **APScheduler** (Python) and **n8n** (visual workflow).

---

## Option 1: APScheduler (Recommended for Production)

### Overview

APScheduler is a Python library that runs scheduled jobs based on cron expressions. It's lightweight, integrated with your Python code, and reliable.

### Features

- Cron-based scheduling
- Reads configuration from `sites.yaml`
- Logs all executions
- Automatic error recovery
- No external dependencies

### Installation

Already included in `requirements.txt`:

```bash
pip install apscheduler
```

### Usage

#### 1. Start the scheduler

```bash
# Activate virtual environment
source venv/bin/activate

# Run scheduler (blocking)
python3 scheduler.py
```

Output:
```
============================================================
Monitor Agent Scheduler Starting
============================================================
Loading 1 site(s) from configuration...
Scheduled: 'surveille les prix sur la page homme de Zalando' with {'hour': 10, 'minute': 0}

Total jobs scheduled: 1

Scheduler running... Press Ctrl+C to stop.
============================================================

Scheduler started
```

#### 2. Configure schedules in sites.yaml

```yaml
sites:
  - instruction: "monitor Zalando prices"
    schedule: "daily 10:00"    # Every day at 10:00 AM
    active: true
    
  - instruction: "track blog posts"
    schedule: "twice-daily"    # 9:00 AM and 6:00 PM
    active: true
    
  - instruction: "check features"
    schedule: "hourly"          # Every hour
    active: false
```

#### 3. Supported schedule formats

| Format | Description | Example |
|--------|-------------|---------|
| `daily HH:MM` | Once per day at specific time | `daily 10:00` |
| `twice-daily` | Twice a day (9am & 6pm) | `twice-daily` |
| `hourly` | Every hour | `hourly` |
| `every X hours` | Every X hours | `every 6 hours` |
| `monday HH:MM` | Specific day of week | `monday 14:30` |

#### 4. Run as background service (production)

**Option A: nohup (simple)**
```bash
nohup python3 scheduler.py > scheduler.log 2>&1 &
```

**Option B: systemd (Linux)**

Create `/etc/systemd/system/monitor-agent.service`:
```ini
[Unit]
Description=Monitor Agent Scheduler
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/monitor_agent
Environment=PATH=/path/to/monitor_agent/venv/bin
ExecStart=/path/to/monitor_agent/venv/bin/python3 scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable monitor-agent
sudo systemctl start monitor-agent
sudo systemctl status monitor-agent
```

**Option C: launchd (macOS)**

Create `~/Library/LaunchAgents/com.monitoragent.scheduler.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.monitoragent.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/monitor_agent/venv/bin/python3</string>
        <string>/path/to/monitor_agent/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/monitor_agent</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/monitor_agent/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/monitor_agent/scheduler.error.log</string>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.monitoragent.scheduler.plist
launchctl start com.monitoragent.scheduler
```

#### 5. View logs

Logs are printed to stdout. When running as a service:

```bash
# systemd (Linux)
sudo journalctl -u monitor-agent -f

# nohup
tail -f scheduler.log

# launchd (macOS)
tail -f /path/to/monitor_agent/scheduler.log
```

---

## Option 2: n8n (Visual Workflow Interface)

### Overview

n8n is an open-source workflow automation tool with a visual interface. It's perfect for:
- Visualizing your automation workflows
- Adding additional integrations (Slack, Discord, webhooks)
- Monitoring execution history with a UI
- Complex workflows with multiple steps

### Installation

#### Prerequisites

- Node.js 18+ required

**Install Node.js (if not installed):**

```bash
# macOS
brew install node

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Windows
# Download from https://nodejs.org
```

#### Option A: Run with npx (no installation)

```bash
npx n8n
```

Then open: http://localhost:5678

#### Option B: Install globally

```bash
npm install -g n8n
n8n start
```

#### Option C: Docker (recommended for production)

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### Setup n8n Workflow

#### 1. Access n8n UI

Open http://localhost:5678 in your browser.

#### 2. Create a new workflow

Click **"New Workflow"**

#### 3. Add a Cron trigger

1. Click the **"+"** button
2. Search for **"Schedule Trigger"**
3. Configure:
   - Mode: `Cron`
   - Cron Expression: `0 10 * * *` (daily at 10:00 AM)

Common cron expressions:
```
0 10 * * *     # Daily at 10:00 AM
0 9,18 * * *   # Twice daily (9 AM & 6 PM)
0 */6 * * *    # Every 6 hours
0 10 * * 1     # Every Monday at 10:00 AM
```

#### 4. Add Execute Command node

1. Click **"+"** after the Schedule node
2. Search for **"Execute Command"**
3. Configure:
   - Command: `cd /path/to/monitor_agent && source venv/bin/activate && python3 main.py`
   - Or use absolute path: `/path/to/monitor_agent/venv/bin/python3 /path/to/monitor_agent/main.py`

#### 5. (Optional) Add error notification

1. Add an **"IF"** node after Execute Command
2. Condition: Check if previous node failed
3. Add **"Gmail"** or **"Slack"** node to send error alert

#### 6. Save and activate

1. Click **"Save"** (top right)
2. Toggle **"Active"** (top right)
3. Your workflow is now running!

### Example Workflow

```
[Schedule Trigger]          [Execute Command]          [IF]
  Every day at 10AM    →    Run main.py          →    Check exit code
                                                        ↓
                                                    [Gmail]
                                                    Send error alert
```

### n8n Workflow JSON

Save this as `n8n-monitor-agent.json` and import in n8n:

```json
{
  "name": "Monitor Agent - Daily Scan",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 10 * * *"
            }
          ]
        }
      },
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "command": "cd /Users/faridgnankambary/Documents/Personal_projects/monitor_agent && source venv/bin/activate && python3 main.py"
      },
      "name": "Run Monitor Agent",
      "type": "n8n-nodes-base.executeCommand",
      "typeVersion": 1,
      "position": [450, 300]
    }
  ],
  "connections": {
    "Schedule Trigger": {
      "main": [
        [
          {
            "node": "Run Monitor Agent",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Comparison: APScheduler vs n8n

| Feature | APScheduler | n8n |
|---------|-------------|-----|
| **Setup complexity** | Low (Python only) | Medium (needs Node.js) |
| **Interface** | CLI/Logs | Web UI |
| **Resource usage** | Very low | Medium (web server) |
| **Monitoring** | Logs only | Visual dashboard |
| **Flexibility** | High (code-based) | Medium (UI-based) |
| **Error handling** | Manual (code) | Visual (workflow) |
| **Best for** | Production, developers | Prototyping, visualization |
| **Dependencies** | Python packages | Node.js, browser |

---

## Recommendations

### For Production (simple & reliable)

Use **APScheduler** with systemd/launchd:
```bash
python3 scheduler.py
```

### For Development & Monitoring

Use **n8n** for visual workflow editing:
```bash
npx n8n
```

### Combined Approach (recommended)

- **APScheduler** as primary scheduler (production)
- **n8n** for additional workflows (Slack notifications, webhooks, etc.)

---

## Troubleshooting

### APScheduler issues

**Problem: Jobs not running**
```bash
# Check logs
python3 scheduler.py

# Verify sites.yaml has active: true
cat config/sites.yaml
```

**Problem: ImportError**
```bash
pip install apscheduler
```

### n8n issues

**Problem: Port 5678 already in use**
```bash
# Use different port
export N8N_PORT=5679
n8n start
```

**Problem: Workflow not triggering**
- Verify workflow is **Active** (toggle in top right)
- Check cron expression is valid
- Check n8n logs in terminal

**Problem: Execute Command fails**
- Use absolute paths (not `~/` or `./`)
- Test command in terminal first
- Check file permissions

---

## Next Steps

1. Test APScheduler locally
2. (Optional) Install n8n and create workflow
3. Choose one for production deployment
4. Set up monitoring/alerts
5. Document your cron schedules

For advanced automation, see the main README.md.
