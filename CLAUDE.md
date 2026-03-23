# Marketing Command Center (MCC)

## What This Is
A local marketing execution platform. Python/FastAPI + Jinja2/HTMX + SQLite.
Runs on localhost:5050. Dark theme. Single process. No Docker.

## Complete Spec
Read MCC-COMPLETE-SPEC.md for the full technical specification.
It contains ALL models, views, integrations, and build phases.

## Tech Stack
- Python 3.14 + FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN)
- SQLite via SQLAlchemy ORM (file: data/mcc.db)
- Chart.js + Sortable.js (CDN)
- Anthropic API for AI features (Claude Sonnet)

## Critical Rules
1. Server-rendered HTML + HTMX. No React/Vue/SPA.
2. SQLite only. No Postgres/Redis.
3. Single Python process. No Docker.
4. Missing API keys = graceful fallback, never crash.
5. Dark theme: bg #0F0F23, cards #1A1A2E, accent #E94560, text #F0F0F0.

## Build Order
Follow phases 1-10 in MCC-COMPLETE-SPEC.md Section 12.
Test each phase before proceeding to the next.

## First Project
Grindlab (poker study SaaS) is pre-loaded via seeds/grindlab.py.
All seed data is defined in MCC-COMPLETE-SPEC.md Section 10.

## MCC SERVICE

MCC runs as a macOS Launch Agent — no terminal needed.
- Plist: ~/Library/LaunchAgents/com.grindlab.mcc.plist
- Starts on login, auto-restarts on crash (KeepAlive: true)
- Logs: ~/marketing-command-center/logs/mcc.log and mcc_error.log
- Manage: `launchctl stop/start com.grindlab.mcc`
- Access: localhost:5050

If MCC won't start, check: `tail -20 ~/marketing-command-center/logs/mcc_error.log`
To kill and restart manually: `lsof -ti:5050 | xargs kill -9 && launchctl start com.grindlab.mcc`

## Local Services Map

This machine runs multiple services. Avoid port conflicts and be aware of background processes.

### Launch Agents (~/Library/LaunchAgents/)

| Label | What | Port | KeepAlive | Logs |
|---|---|---|---|---|
| `com.grindlab.mcc` | MCC (this project) | 5050 | Yes | `~/marketing-command-center/logs/` |
| `ai.openclaw.gateway` | OpenClaw Gateway | — | Yes | `~/.openclaw/logs/` |
| `com.scotty.dashboard` | Scotty Dashboard (Node) | 3000 | Yes | `~/scotty-dashboard/logs/` |
| `com.scotty.automation` | Scotty automation master — every 15 min | — | No | `~/clawd/logs/local-automation*.log` |

**Unloaded agents** (disabled 2026-03-08, scripts missing from disk):
- `com.philgiliam.scotty-autonomous` — scotty-daemon.sh not found
- `com.scotty.nightly` — nightly-execution-master.sh not found
| `com.n8n.start` | n8n workflow automation | 5678 | Yes | `~/clawd/logs/n8n*.log` |

Ollama also runs on port 11434 (system-managed).

### Reserved Ports

| Port | Service |
|---|---|
| 3000 | Scotty Dashboard |
| 5050 | MCC |
| 5678 | n8n |
| 11434 | Ollama |

Do NOT bind new services to these ports.

### Cron Jobs (crontab -l)

**MCC:**
- `3 AM daily` — MCC daily backup (`scripts/daily_backup.sh`)
- `Every 30 min` — MCC heartbeat ping to Healthchecks.io (`scripts/heartbeat_ping.sh`)

**Clawd/Grindlab marketing:**
- `1 AM daily` — clawd system backup
- `7:00 AM daily` — Reddit daily brief
- `7:05 AM daily` — Pipeline health check
- `7:15 AM daily` — YouTube comment targets
- `7:20 AM daily` — Forum comment targets
- `Every 4 hrs` — Milestone alerts
- `Monday 8 AM` — Outreach discovery
- `Sunday 8 AM` — Weekly metrics rollup
- `Sunday 9 PM` — Landscape monitor

Full automation details: see SCOTTY-AUTOMATION-REFERENCE.md

## Related Systems
- Clawd/Scotty workspace at ~/clawd/ runs cron jobs that feed data into MCC via /api/metrics/record and /api/automations/heartbeat endpoints.
- 9 Grindlab cron jobs run in macOS crontab (reddit brief, pipeline health, youtube targets, forum targets, milestone alerts, weekly rollup, outreach discovery, landscape monitor, backup).
- All Python cron jobs MUST use /opt/homebrew/bin/python3, never system python.
- Current focus: Grindlab launch April 1, 2026.

## Documentation Sync
When Phil says "update docs" or "sync docs", review everything that changed this session and update CLAUDE.md to reflect the current state. Do not update CLAUDE.md until explicitly told to.

## Key Documents
- **MCC-PRODUCT-BRD.md** — Comprehensive product BRD (current state audit, architecture, integrations, automation engine, known issues, travel-proof requirements, multi-product vision, costs). Use this as the primary reference for MCC development decisions.
- **MCC-COMPLETE-SPEC.md** — Full technical specification with all models, views, integrations, and build phases.
- **SCOTTY-AUTOMATION-REFERENCE.md** — All external automations, cron jobs, and launch agents.

## Session Startup
- Read SYSTEM-STATUS.md for current infrastructure state before starting any session.
