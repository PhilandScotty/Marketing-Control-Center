# SYSTEM-STATUS.md
**Generated:** 2026-03-23 06:00
**Host:** Phils-Mac-mini.local

## Service Health (Port Check)

| Port | Service | Status |
|------|---------|--------|
| 5050 | MCC (Marketing Command Center) | + UP |
| 18789 | OpenClaw Gateway | + UP |
| 5678 | n8n Workflow Automation | + UP |
| 3000 | Scotty Dashboard | X DOWN |

## LaunchAgents

- `com.scotty.automation` — PID -, exit 0 (not running)
- `com.grindlab.reddit-brief` — PID -, exit 0 (not running)
- `com.n8n.start` — PID 1018, exit 0 (running)
- `com.scotty.dashboard` — PID 1009, exit 0 (running)
- `ai.openclaw.gateway` — PID 1006, exit 0 (running)
- `com.grindlab.mcc` — PID 1016, exit 0 (running)

## Crontab Entries

- `0 1 * * *` — backup-system.sh
- `0 7 * * *` — reddit_daily_brief.py
- `0 */4 * * *` — milestone_alerts.py
- `0 8 * * 0` — weekly_metrics_rollup.py
  # MCC daily auto-backup (code + database)
- `0 3 * * *` — daily_backup.sh
  # MCC dead man's switch — pings Healthchecks.io every 30min
- `*/30 * * * *` — heartbeat_ping.sh
- `15 7 * * *` — youtube_comment_targets.py
- `20 7 * * *` — forum_comment_targets.py
  # Weekly outreach discovery — Monday 8AM MST
- `0 8 * * 1` — outreach_discovery.py
  # Weekly landscape monitor — Sunday 9PM MST
- `0 21 * * 0` — landscape_monitor.py
  # MCC Alert Bridge — morning + evening critical insight alerts
- `30 7 * * *` — mcc-alert-bridge.py
- `0 18 * * *` — mcc-alert-bridge.py
  # Cron Health Watchdog — daily 8 AM stale log check
- `0 8 * * *` — cron-health-watchdog.py
  # Grindlab Content Monitor — daily content generation (migrated from OpenClaw)
- `25 7 * * *` — grindlab-content-monitor.sh
  # Strategic Research — Mon/Thu 10 AM (migrated from OpenClaw)
- `0 10 * * 1,4` — strategic-research.py
  # System Status Sync — daily 6 AM infrastructure snapshot
- `0 6 * * *` — sync-system-status.py
  # Daily SEO Health Check — 6AM MST
- `0 6 * * *` — seo_health_check.py
  # Scotty Heartbeat Monitor — daily 7:15 AM watchdog
- `15 7 * * *` — scotty_heartbeat.py
  # Kit CTA swap reminder — one-shot March 31 9AM MST (remove after)
- `0 9 31 3 *` — kit_cta_swap_reminder.py
- `5 7 * * *` — pipeline_health_check.py

**Total entries:** 20

## Grindlab Log Freshness

| Log File | Last Modified | Age |
|----------|---------------|-----|
| content_monitor.log | 2026-03-22 07:25 | 22.6h ago |
| forum_targets.log | 2026-03-22 07:20 | 22.7h ago |
| influencer_enrichment.log | 2026-03-06 13:23 | 16.7d ago **STALE** |
| landscape_monitor.log | 2026-03-22 21:00 | 9.0h ago |
| milestone_alerts.log | 2026-03-23 04:00 | 2.0h ago |
| milestones_reached.json | 2026-03-23 04:00 | 2.0h ago |
| outreach_discovery.log | 2026-03-16 08:00 | 6.9d ago **STALE** |
| pipeline_health.log | 2026-03-22 07:05 | 22.9h ago |
| pipeline_history.json | 2026-03-22 07:05 | 22.9h ago |
| reddit_brief.log | 2026-03-22 07:00 | 23.0h ago |
| reddit_brief_launchd.log | 2026-03-22 07:00 | 23.0h ago |
| reddit_engaged.log | 2026-03-04 12:37 | 18.7d ago **STALE** |
| scotty_heartbeat.log | 2026-03-22 07:15 | 22.7h ago |
| seo_health.log | 2026-03-22 06:01 | 24.0h ago |
| weekly_metrics.json | 2026-03-22 08:00 | 22.0h ago |
| weekly_metrics.log | 2026-03-22 08:00 | 22.0h ago |
| youtube_targets.log | 2026-03-22 07:15 | 22.7h ago |

## Clawd Core Logs

| Log File | Last Modified | Age |
|----------|---------------|-----|
| ~/clawd/logs/backup.log | 2026-03-23 01:01 | 5.0h ago |
| ~/clawd/logs/local-automation.log | 2026-03-23 05:53 | 7m ago |
| ~/clawd/logs/mcc-alert-bridge.log | 2026-03-22 18:00 | 12.0h ago |
| ~/clawd/logs/cron-watchdog.log | 2026-03-22 08:00 | 22.0h ago |
| ~/clawd/logs/strategic-research.log | 2026-03-19 10:00 | 3.8d ago **STALE** |
| ~/marketing-command-center/data/backups/backup.log | 2026-03-23 03:00 | 3.0h ago |

## MCC Error Log (last 10 lines)

File size: 726,215 bytes | Last modified: 0m ago

```
INFO:httpx:HTTP Request: POST https://api.buffer.com "HTTP/1.1 200 OK"
INFO:mcc.auto_metrics:Auto-metric: posts_published=1.0 for channel_id=6
INFO:mcc.auto_metrics:Auto-metric: posts_published=1.0 for channel_id=10
INFO:apscheduler.executors.default:Job "Refresh buffer (trigger: interval[4:00:00], next run at: 2026-03-23 08:07:57 MDT)" executed successfully
INFO:apscheduler.executors.default:Running job "Ai Anomaly Detector (trigger: cron[hour='6'], next run at: 2026-03-24 06:00:00 MDT)" (scheduled at 2026-03-23 06:00:00-06:00)
INFO:apscheduler.executors.default:Running job "Status Export (trigger: cron[hour='6', minute='0'], next run at: 2026-03-24 06:00:00 MDT)" (scheduled at 2026-03-23 06:00:00-06:00)
INFO:mcc.ai.jobs:Anomaly detector completed
INFO:apscheduler.executors.default:Job "Ai Anomaly Detector (trigger: cron[hour='6'], next run at: 2026-03-24 06:00:00 MDT)" executed successfully
INFO:mcc.status_export:Status export written to /Users/philgiliam/clawd/projects/grindlab/MCC-STATUS.md
INFO:apscheduler.executors.default:Job "Status Export (trigger: cron[hour='6', minute='0'], next run at: 2026-03-24 06:00:00 MDT)" executed successfully
```

## OpenClaw Scheduled Jobs

- [disabled] `0 2 * * *` — Nightly Data Protection
- [disabled] `0 8 * * *` — Morning Briefing - Data Protection Status
- [disabled] `0 23 * * *` — Nightly Autonomous Improvement
- [disabled] `0 8 * * *` — Phil Help Analysis Tomorrow Morning
- [ENABLED] `0 */3 * * *` — Heartbeat Poll (3hr)
- [disabled] `0 7 * * *` — grindlab-content-monitor
- [disabled] `0 10 * * 1,4` — Strategic Research - Mon/Thu

