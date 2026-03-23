# Scotty Automation Reference

> Last verified: 2026-03-08
> Source of truth: `crontab -l`, `~/Library/LaunchAgents/`, disk audit of `~/clawd/`

## Launch Agents

### Active (loaded and running)

| Label | What | Schedule | Port | Logs |
|---|---|---|---|---|
| `com.grindlab.mcc` | MCC (Marketing Command Center) | Always on (KeepAlive) | 5050 | `~/marketing-command-center/logs/` |
| `ai.openclaw.gateway` | OpenClaw Gateway | Always on (KeepAlive) | — | `~/.openclaw/logs/` |
| `com.scotty.dashboard` | Scotty Dashboard (Node.js) | Always on (KeepAlive) | 3000 | `~/scotty-dashboard/logs/` |
| `com.n8n.start` | n8n workflow automation | Always on (KeepAlive) | 5678 | `~/clawd/logs/n8n*.log` |
| `com.scotty.automation` | Local automation master | Every 15 min (StartInterval) | — | `~/clawd/logs/local-automation*.log` |

### Unloaded (disabled 2026-03-08)

Plists still exist in `~/Library/LaunchAgents/` but are disabled via `launchctl disable`. Scripts were missing from disk.

| Label | Missing Script | Original Schedule |
|---|---|---|
| `com.philgiliam.scotty-autonomous` | `~/clawd/scripts/scotty-daemon.sh` | Every 5 min |
| `com.scotty.nightly` | `~/clawd/scripts/nightly-execution-master.sh` | 11 PM daily |

To re-enable: recreate the scripts, then `launchctl enable gui/<uid>/<label>` and `launchctl bootstrap gui/<uid> <plist>`.

## Cron Jobs

### MCC (this project)

| Schedule | Command | Log |
|---|---|---|
| 3 AM daily | `scripts/daily_backup.sh` — code + database backup | `data/backups/backup.log` |
| Every 30 min | `scripts/heartbeat_ping.sh` — dead man's switch to Healthchecks.io | `data/backups/heartbeat.log` |

### Clawd System

| Schedule | Command | Log |
|---|---|---|
| 1 AM daily | `~/clawd/scripts/backup-system.sh` — full clawd backup | `~/clawd/logs/backup.log` |

### Grindlab Marketing (~/clawd/projects/grindlab/)

| Schedule | Script | What It Does |
|---|---|---|
| 7:00 AM daily | `reddit_daily_brief.py` | Reddit daily brief — scans subreddits for Grindlab-relevant posts |
| 7:05 AM daily | `pipeline_health_check.py` | Pipeline health check — validates marketing pipeline status |
| 7:15 AM daily | `youtube_comment_targets.py` | YouTube comment targets — finds videos to engage with |
| 7:20 AM daily | `forum_comment_targets.py` | Forum comment targets — finds forum threads for outreach |
| Every 4 hours | `milestone_alerts.py` | Milestone alerts — checks project milestones and alerts |
| Sunday 8 AM | `weekly_metrics_rollup.py` | Weekly metrics rollup — aggregates weekly performance data |
| Sunday 9 PM | `landscape_monitor.py` | Landscape monitor — competitive/market landscape scan |
| Monday 8 AM | `outreach_discovery.py` | Outreach discovery — finds new outreach opportunities |

### Scripts on Disk But NOT Scheduled

These scripts exist in `~/clawd/projects/grindlab/` with no cron entry. They are **intentionally on-demand only** — do not schedule them.

| Script | Purpose |
|---|---|
| `morning_dashboard_brief.py` | Morning dashboard brief via Telegram/Scotty |
| `influencer_enrichment.py` | Influencer enrichment — enriches influencer data |
| `import_to_mcc.py` | Imports enriched influencers to MCC outreach pipeline |

### One-Time Utility Scripts (not automations)

These are patch/fix scripts, not recurring automations:

- `final_fix.py` — one-time fix for reddit_daily_brief.py
- `patch_brief.py` — one-time patch for reddit_daily_brief.py
- `patch_dedup.py` — one-time dedup fix for reddit_daily_brief.py

## Reserved Ports

| Port | Service |
|---|---|
| 3000 | Scotty Dashboard |
| 5050 | MCC |
| 5678 | n8n |
| 11434 | Ollama (system) |

Do NOT bind new services to these ports.

## Scotty Automation Master Details

`com.scotty.automation` runs `~/clawd/scripts/local-automation-master.sh` every 15 min.
- Only active during the **automation window** (Friday 5 PM → Monday 8 AM) unless manually overridden
- Override: set `"override": "enabled"` in `~/clawd/memory/automation-schedule.json`
- Runs improvement cycles, queues messages to `~/clawd/memory/message-queue/`
