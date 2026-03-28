# Marketing Control Center (MCC)

Centralized marketing operations dashboard — outreach pipeline, tech stack tracking, budget management, and campaign coordination.

## What This Is

MCC is the central hub for managing marketing operations across products. It tracks channels, tasks, automations, content pipelines, ad campaigns, subscribers, experiments, competitors, and budgets — all from a single dark-themed dashboard at `localhost:5050`.

## Tech Stack

- **Backend:** Python 3.14 + FastAPI + SQLAlchemy ORM
- **Frontend:** Jinja2 + HTMX + Tailwind CSS (CDN) + Chart.js
- **Database:** SQLite (`data/mcc.db`)
- **AI:** Anthropic Claude API for insights, analysis, and chat
- **Scheduling:** APScheduler for background jobs
- **External Tools:** Autonomous tool API for bots like Scotty

## Quick Start

```bash
cd ~/Marketing-Control-Center
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 5050
```

Or use the Dock app: `Marketing Command Center.app`

### Windows Local Dev

```powershell
cd C:\Projects\Marketing-Control-Center
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Open [http://localhost:5050](http://localhost:5050) after startup.

### Optional `.env`

MCC calls `load_dotenv()` from `app/config.py`, so you can place a `.env` file in the repo root for local secrets. Most integrations are optional; the app should still boot without them and fall back to manual workflows.

## Multi-Project Architecture

Each project lives in the database. Seed files are backups and templates.

```
Marketing-Control-Center/          # The platform (engine)
├── app/                           # Application code
├── seeds/                         # One seed file per project
│   ├── grindlab.py                # Grindlab seed (hand-written)
│   ├── grindlab_export.py         # Grindlab snapshot (auto-exported)
│   └── future_project.py          # Next product seed
├── data/
│   ├── mcc.db                     # Runtime database (gitignored)
│   └── backups/                   # Daily DB backups (gitignored)
├── scripts/
│   └── daily_backup.sh            # Auto-commit + DB backup cron
└── manage.py                      # Management commands
```

**What gets committed:** Code, templates, seeds, config, scripts.
**What does NOT get committed:** Database, backups, `.env`, `venv/`.

### Starting a New Project

**Option A — Use the wizard:**
Navigate to `/wizard` in MCC. Creates the project in the existing database.

**Option B — Create a seed file:**
Write a new `seeds/my_project.py` following the pattern in `seeds/grindlab.py`. Register it in `app/main.py` startup.

### Exporting a Project Snapshot

```bash
python manage.py export-seed --project grindlab > seeds/grindlab_export.py
```

This exports the current state of any project as a Python seed file — a snapshot that can fully recreate the project from scratch in a fresh database. Useful for:
- Backing up project configuration as code
- Sharing project templates
- Rebuilding after a database reset

## Management Commands

```bash
# Export project status as markdown
python manage.py export-status

# Export project as a seed file
python manage.py export-seed --project <slug>
```

## Autonomous Tools API

External bots and cron systems register as Connected Tools and report via authenticated API.

```bash
# Heartbeat (health check-in)
curl -X POST http://localhost:5050/api/tools/heartbeat \
  -H "X-Api-Key: <tool-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"status":"online","message":"All systems nominal"}'

# Report metrics
curl -X POST http://localhost:5050/api/tools/metrics \
  -H "X-Api-Key: <tool-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"metrics":[{"metric_name":"posts_scraped","value":42}]}'

# Send alert (creates AI Insight on dashboard)
curl -X POST http://localhost:5050/api/tools/alert \
  -H "X-Api-Key: <tool-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"severity":"attention","title":"Rate limit approaching"}'
```

Manage tools at `/tools` in the UI. Each tool gets a unique API key.

## Daily Backup

Runs at 3AM via cron (`scripts/daily_backup.sh`):
1. Backs up `data/mcc.db` to `data/backups/mcc_YYYYMMDD.db` (14-day retention)
2. `git add -A && git commit` (skips if no changes)
3. `git push origin main`
4. Sends heartbeat to MCC

## Environment Variables

Create a `.env` file or set these in your shell:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export CONVERTKIT_API_SECRET="..."
export INSTANTLY_API_KEY="..."
export GA4_CREDENTIALS_PATH="/path/to/service-account.json"
export GA4_PROPERTY_ID="..."
export BUFFER_ACCESS_TOKEN="..."
export STRIPE_API_KEY="sk_live_..."
```

Missing keys are fine — integrations fall back to manual entry.
GA4 setup may also require `cryptography`, but only if you want the GA4 integration enabled locally.

## Key Pages

| Page | URL | Purpose |
|------|-----|---------|
| Dashboard | `/` | Execution score, channel health, urgent items, AI insights |
| Daily Ops | `/daily` | Today's checklist and priorities |
| Tasks | `/tasks` | Kanban board with drag-and-drop |
| Content | `/pipelines/content` | Content production pipeline |
| Ads | `/ads` | Ad campaign management with signals |
| Automations | `/automations` | Automation registry and health timeline |
| Connected Tools | `/tools` | External bot/tool registry |
| AI Chat | Sidebar panel | Claude-powered marketing assistant |
| Subscribers | `/subscribers` | Subscriber funnel and cohort analysis |
| Budget | `/budget` | Budget allocation and spend tracking |
| Experiments | `/experiments` | A/B test tracking |
| Strategy | `/strategy` | Marketing strategy documentation |

## First Project

**Grindlab** — poker study SaaS (grindlab.ai). Pre-loaded via `seeds/grindlab.py` with 14 channels, 45 tasks, 11 automations, 6 email sequences, 3 ad campaigns, 10 outreach contacts, and 4 competitors.
