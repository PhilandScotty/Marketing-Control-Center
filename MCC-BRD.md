# Marketing Command Center (MCC) — Business Requirements Document

**Document Date:** 2026-03-08
**Version:** 1.0
**Author:** Generated from codebase audit
**Project Owner:** Phil Gilliam

---

## 1. What MCC Is and What Problem It Solves

MCC is a local desktop marketing execution platform built for a solo marketing operator. It runs on a Mac Mini at `localhost:5050` as a persistent macOS Launch Agent.

**Problem:** A one-person marketing operation across 14+ channels, 17+ tools, 10+ automations, and 40+ tasks has too many moving parts. Things fall through the cracks — stale automations go unnoticed, follow-ups are missed, content pipelines stall, deadlines compound, and there is no single place to see what's broken, what's working, and what needs attention next.

**Solution:** MCC consolidates all marketing channels, tasks, automations, metrics, content, outreach, ads, and budget into one system. It adds an AI-powered "execution guarantee" layer that monitors for anomalies, missed deadlines, stale automations, and compounding failures — then surfaces them as actionable alerts before they become problems.

**First project:** Grindlab (poker study SaaS at grindlab.ai), with a launch date of April 1, 2026. The system is project-based and designed to support future products.

---

## 2. Architecture

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.14, FastAPI |
| Frontend | Jinja2 templates + HTMX + Tailwind CSS (CDN) |
| Database | SQLite via SQLAlchemy ORM (`data/mcc.db`) |
| Scheduler | APScheduler (in-process) |
| AI Engine | Anthropic API (Claude Sonnet 4) |
| Charts | Chart.js (CDN) |
| Drag/Drop | Sortable.js (CDN) |
| HTTP Client | httpx (async) |
| Fonts | Inter (Google Fonts CDN) |

### Constraints

- Server-rendered HTML + HTMX. No React/Vue/SPA.
- SQLite only. No Postgres/Redis.
- Single Python process. No Docker.
- Missing API keys = graceful fallback, never crash.
- Dark theme with fixed color palette.

### Process Model

- Runs as macOS Launch Agent (`com.grindlab.mcc`) with `KeepAlive: true`
- Auto-restarts on crash
- Logs to `~/marketing-command-center/logs/`
- Port 5050 (reserved)

### Data Model

34+ SQLAlchemy models including: Project, Channel, Tool, Task, Automation, EmailSequence, AdCampaign, ContentPiece, Metric, MetricSnapshot, AIInsight, OutreachContact, ChatConversation, ChatMessage, PartnerView, SubscriberSnapshot, SubscriberEvent, ContentTag, PerformanceScore, ProjectStrategy, BudgetAllocation, BudgetExpense, BudgetLineItem, BudgetMonthEntry, Competitor, CompetitorUpdate, KnowledgeEntry, Experiment, LeadScore, CustomerFeedback, OnboardingMilestone, OnboardingProgress, AutonomousTool, MorningBrief, ApprovalQueueItem, LaunchTemplate, TemplateTask, BrandColor, BrandFont, PlatformProfile, BrandGuidelines, MonthlyRevenue.

All models are project-scoped (FK to Project) except KnowledgeEntry (can be global) and ChatConversation/ChatMessage.

### Route Modules (33 registered routers)

dashboard, channels, metrics, subscribers, ai, tasks, roadmap, daily, calendar_view, weekly, automations, pipelines, feedback, ads, techstack, budget, experiments, whats_working, api, chat, strategy, knowledge, competitors, partner, retention, wizard, search, tools_api, tools_mgmt, settings, checklist, templates, brand, track, strategy_export, discovery, intelligence, website, queue.

---

## 3. Current Features and Status

### Operations (Check Status)

| Feature | Route | Status | Description |
|---------|-------|--------|-------------|
| Dashboard | `/` | Live | Execution score (0-100), channel health grid, urgent items, AI insights panel, launch countdown, morning brief, MRR tracking, budget summary |
| Daily Ops | `/daily` | Live | Morning briefing with today's tasks, automation status, overnight alerts |
| Calendar | `/calendar` | Live | Unified marketing calendar aggregating content, emails, ads, events |
| Roadmap | `/roadmap` | Live | Timeline view with tasks, due dates, dependency tracking |
| Weekly Review | `/weekly` | Live | Full metrics review with task velocity, channel performance |

### Execution (Do Work)

| Feature | Route | Status | Description |
|---------|-------|--------|-------------|
| Tasks | `/tasks` | Live | Kanban board (7 columns: backlog, this_week, in_progress, blocked, done, monitoring, recurring/archived). Drag-and-drop via Sortable.js. Create/edit modals, dependency fields, recurring task auto-generation, task archiving with completion dates |
| Content Pipeline | `/pipelines/content` | Live | Content pipeline kanban (concept → published), content prep with AI-drafted social posts |
| Outreach Pipeline | `/pipelines/outreach` | Live | Influencer/ambassador/affiliate pipeline with follow-up tracking, auto-drafted follow-ups via Approval Queue |
| Ads | `/ads` | Live | Campaign management with automated signal system (scale/hold/optimize/pause/kill) |
| Approval Queue | `/queue` | Live | Human-in-the-loop queue for AI-generated content drafts, outreach follow-ups, and automated actions |

### Intelligence (Analyze)

| Feature | Route | Status | Description |
|---------|-------|--------|-------------|
| What's Working | `/whats-working` | Live | Messaging analysis, content performance tracking |
| Subscribers | `/subscribers` | Live | Funnel visualization, subscriber snapshots by stage |
| Retention | `/retention` | Live | Retention segments view |
| Feedback | `/feedback` | Live | Customer feedback with testimonials |
| Competitors | `/competitors` | Live | Competitive intelligence with competitor profiles, updates |
| Intelligence | `/intelligence` | Live | Cross-channel intelligence view |
| Website | `/website` | Live | Website intelligence with scheduled analysis job |

### System (Manage)

| Feature | Route | Status | Description |
|---------|-------|--------|-------------|
| Channels | `/channels` | Live | Channel CRUD + detail views with metric charts. 14 channels seeded |
| Automations | `/automations` | Live | Automation registry with health indicators, staleness detection |
| Tech Stack | `/techstack` | Live | Tool management with gap/redundancy detection. 17+ tools seeded |
| Budget | `/budget` | Live | Budget planner with allocation, actual vs planned, auto-fill for fixed subscriptions |
| Strategy | `/strategy` | Live | Strategy document builder with AI conversation, strategy export |
| Settings | `/settings` | Live | API key configuration, thresholds, integration status |
| Brand | `/brand` | Live | Brand guidelines, colors, fonts, platform profiles |
| Templates | `/templates` | Live | Launch templates with template tasks |

### Global Features

| Feature | Route | Status | Description |
|---------|-------|--------|-------------|
| AI Chat | `/chat` | Live | Slide-out panel with full conversation history, tool calling (16+ tools), page-context awareness |
| Knowledge Base | `/knowledge` | Live | Cross-project knowledge entries (lessons, decisions, playbooks, benchmarks) |
| Search | `/search` | Live | Global search across entity types |
| Wizard | `/wizard` | Live | Project setup wizard |
| Partner View | `/partner` | Live | Shareable read-only dashboards with token-based access |
| Discovery | `/discovery` | Live | Discovery/exploration tools |
| Metrics API | `/api/metrics/record` | Live | External metric push endpoint (used by Scotty scripts) |
| Automation Heartbeat | `/api/automations/heartbeat` | Live | External automation health reporting endpoint |
| Tools API | `/api/tools/*` | Live | Autonomous tool heartbeat, metrics, and management endpoints |

---

## 4. Integrations and Data Sources

### API Integrations (In-Process via APScheduler)

| Integration | Data Pulled | Refresh Interval | Env Var | Status |
|------------|------------|-------------------|---------|--------|
| ConvertKit | Subscribers, new today, by tag, sequence open/click rates | 4 hours | `CONVERTKIT_API_SECRET` | Live (configured) |
| Instantly | Sent, opens, replies, bounces | 6 hours | `INSTANTLY_API_KEY` | Live (configured) |
| GA4 (Google Analytics) | Pageviews, sessions, conversions, sources | 6 hours | `GA4_CREDENTIALS_PATH` + `GA4_PROPERTY_ID` | Live (configured) |
| Buffer | Queue count, sent posts, engagement, social metrics via GraphQL | 4 hours | `BUFFER_ACCESS_TOKEN` | Live (configured) |
| Stripe | MRR, trials, conversion rate, churn | 4 hours | `STRIPE_API_KEY` | Framework ready, pre-launch |
| Meta Ads | Spend, impressions, clicks, CTR, CPL, ROAS | 6 hours | `META_ADS_ACCESS_TOKEN` | Framework ready |
| Reddit Ads | Spend, impressions, clicks, CTR, CPL | 6 hours | `REDDIT_ADS_TOKEN` | Framework ready |
| Google Ads | Spend, impressions, clicks, CTR, video views | 6 hours | `GOOGLE_ADS_CREDENTIALS` | Framework ready |

### Additional Data Sources (No Dedicated Integration Class)

| Source | Method | Env Var | Status |
|--------|--------|---------|--------|
| YouTube Data API | Direct API call in `auto_metrics.py` | `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID` | Live |
| Reddit (karma scrape) | Public JSON endpoint, no auth | `REDDIT_USERNAME` | Live |
| Hunter.io | Contact enrichment | `HUNTER_API_KEY` | Configured, used on-demand |
| SparkLoop | Referral data | `SPARKLOOP_API_KEY` | Framework ready |
| Railway | Workflow health | `RAILWAY_API_KEY` | Framework ready |

### Integration Architecture

All integrations inherit from `IntegrationBase` which provides:
- `is_configured()` — checks if required env vars are set
- `connect()` — verifies connectivity
- `fetch_metrics()` — pulls data and returns `MetricReading` objects
- Exponential backoff retry (3 attempts, rate-limit handling)
- Consecutive failure tracking → health status (healthy/warning/critical)
- Graceful fallback: missing API key = skip, not crash

### External Push APIs

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `POST /api/metrics/record` | Scotty scripts push metrics directly to MCC | API key |
| `POST /api/automations/heartbeat` | Scotty reports automation execution health | API key |
| `POST /api/tools/heartbeat` | Autonomous tool (Scotty) health reporting | API key |
| `POST /api/tools/metrics` | Autonomous tool metric reporting | API key |

### Alert System (3 Levels)

| Level | Method | Status |
|-------|--------|--------|
| Level 1: Dashboard | Internal AIInsight records (staleness, anomalies, deadlines) | Always active |
| Level 2: Telegram | Bot alerts for critical/warning events | Requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| Level 3: Healthchecks.io | External dead man's switch — if Mac Mini stops pinging, external alert fires | Requires `HEALTHCHECKS_PING_URL` |

### AI Engine

- Provider: Anthropic API (Claude Sonnet 4, model `claude-sonnet-4-20250514`)
- Direct HTTP calls via httpx (not SDK)
- System prompt with Grindlab context
- 16+ tool definitions for chat (get_channel_metrics, create_task, record_metric, get_execution_score, track_entity, etc.)
- Page-context awareness: chat knows which view the user is on
- Estimated cost: ~$12/month
- All AI features degrade gracefully without `ANTHROPIC_API_KEY`

---

## 5. Scheduled Jobs and Cron

### In-Process Jobs (APScheduler, runs inside MCC)

#### Integration Refresh Jobs

| Job | Schedule | What It Does |
|-----|----------|-------------|
| ConvertKit refresh | Every 4 hours | Pull subscriber counts, tag data, sequence metrics |
| Instantly refresh | Every 6 hours | Pull send/open/reply/bounce metrics |
| GA4 refresh | Every 6 hours | Pull pageviews, sessions, conversions |
| Buffer refresh | Every 4 hours | Pull queue count, social metrics |
| Stripe refresh | Every 4 hours | Pull MRR, trials, churn (post-launch) |
| Meta/Reddit/Google Ads | Every 6 hours | Pull ad spend, impressions, clicks (when configured) |

#### AI Monitoring Jobs

| Job | Schedule | What It Does |
|-----|----------|-------------|
| Deadline Enforcer | Every 6 hours | Checks tasks: 48h reminder, 24h warning, overdue alert, dependency chain analysis |
| Anomaly Detector | Daily 6 AM | Compares metrics to 7-day avg, flags >15% deviations |
| Automation Health | Every 4 hours | Checks all automations for staleness (1.5x/3x expected interval) |
| Ad Signal Calculator | Every 6 hours | Recalculates campaign signals (scale/hold/optimize/pause/kill) |
| Gap Analyzer | Weekly (Sunday 6 AM) | Structural + strategic gap analysis (channels with no tasks, budget overruns, tool gaps, etc.) |
| Weekly Digest | Sunday 7 AM | Full project summary with execution score, task/content/channel stats |
| Outreach Follow-Up | Daily 8 AM | Flags overdue contact follow-ups |
| Content Pipeline Check | Daily 9 AM | Checks content output vs weekly target (3/week) |
| Lead Scoring | Weekly (Sunday 5 AM) | Scores leads based on activity with decay for inactivity |
| Channel Intelligence | Weekly (Sunday 6:30 AM) | Channel performance digest, WoW comparisons, stale nudges, Telegram summary |
| Channel Metric Monitor | Every 6 hours | Checks for >20% drops in primary channel metrics |
| Morning Brief | Daily 7 AM | Generates morning briefing for dashboard |
| Social Metrics | Every 6 hours | YouTube subscribers, Reddit karma, Buffer social metrics |
| Status Export | Daily 6 AM | Writes `MCC-STATUS.md` to `~/clawd/projects/grindlab/` |
| Strategy Export | Weekly (Sunday 6 AM) | Exports strategy document |
| Website Intelligence | Weekly (Sunday 7:30 AM) | Website analysis job |
| Outreach Workflow | Daily 8:30 AM | Auto-drafts follow-ups, surfaces decline checks in Approval Queue |
| Content Prep | Weekly (Saturday 9 AM) | AI-generates 5-7 draft social posts, places in Approval Queue |

#### Total: 8 integration refresh jobs + 18 AI/monitoring jobs = 26 scheduled jobs

### External Cron Jobs (macOS crontab)

| Schedule | Script | What It Does |
|----------|--------|-------------|
| 3 AM daily | `scripts/daily_backup.sh` | SQLite database backup (14-day retention), git auto-commit, push to GitHub, heartbeat to MCC |
| Every 30 min | `scripts/heartbeat_ping.sh` | Dead man's switch ping to Healthchecks.io |

### External Cron Jobs (Clawd/Grindlab Marketing, separate system)

| Schedule | Script | Purpose |
|----------|--------|---------|
| 1 AM daily | `backup-system.sh` | Clawd system backup |
| 7:00 AM daily | `reddit_daily_brief.py` | Reddit subreddit scanning |
| 7:05 AM daily | `pipeline_health_check.py` | Marketing pipeline validation |
| 7:15 AM daily | `youtube_comment_targets.py` | YouTube engagement targets |
| 7:20 AM daily | `forum_comment_targets.py` | Forum outreach targets |
| Every 4 hours | `milestone_alerts.py` | Project milestone checking |
| Monday 8 AM | `outreach_discovery.py` | New outreach opportunity discovery |
| Sunday 8 AM | `weekly_metrics_rollup.py` | Weekly performance aggregation |
| Sunday 9 PM | `landscape_monitor.py` | Competitive/market landscape scan |

### Launch Agents (macOS)

| Agent | Service | Port | KeepAlive |
|-------|---------|------|-----------|
| `com.grindlab.mcc` | MCC (this project) | 5050 | Yes |
| `ai.openclaw.gateway` | OpenClaw Gateway | — | Yes |
| `com.scotty.dashboard` | Scotty Dashboard (Node.js) | 3000 | Yes |
| `com.n8n.start` | n8n workflow automation | 5678 | Yes |
| `com.scotty.automation` | Automation master (15-min cycles, weekends only) | — | No |

---

## 6. Seed Data (Grindlab Project)

Pre-loaded on first run via `seeds/grindlab.py`:

| Entity | Count | Details |
|--------|-------|---------|
| Channels | 14 | 8 live (Email, Cold Email, Quiz, Reddit, X/Twitter, Instagram, YouTube, SparkLoop), 6 planned (Influencer, TikTok, Rumble, Paid Ads, Ambassador, Affiliate) |
| Tools | 17+ | ConvertKit, Instantly, Railway, Buffer, X Premium, SparkLoop, GA4, GTM, Meta Pixel, Hotjar, Vercel, Supabase, etc. |
| Tasks | 40+ | Full backlog from Master Brief with priorities, assignees, due dates, dependency chains |
| Automations | 10+ | Reddit Daily Brief, Milestone Alerts, Weekly Rollup, Kit Nurture, n8n pipelines, Buffer posts, etc. |
| Email Sequences | 6 | 3 live (Nurture v3, Leak Finder Results, Lead Magnet Delivery), 3 not built (Launch Countdown, Trial Expiration, Onboarding Activation) |
| Competitors | 4 | Upswing Poker, PokerCoaching.com, GTO Wizard, Run It Once |
| Outreach Contacts | 10 | Top priority influencers (Lexy Gavin-Mather 289K, hungry horse poker 184K, +8 more) |
| Onboarding Milestones | 8 | Complete Leak Finder → Trial Day 25+ conversion window |
| Brand Assets | Yes | Colors, fonts, platform profiles, brand guidelines |
| Launch Templates | Yes | Reusable project templates with template tasks |

---

## 7. Execution Guarantee System

The core value proposition — automated monitoring that prevents compounding failures.

### Execution Score (0-100)

| Component | Weight | How It Scores |
|-----------|--------|---------------|
| Tasks on track | 25% | -5 per overdue, -10 per launch-critical overdue |
| Automations healthy | 20% | -15 per stale, -25 per failed |
| Channels healthy | 20% | -10 per warning, -20 per critical |
| Content pipeline | 15% | Proportional to weekly target (3/week) |
| Recurring tasks done | 10% | Proportional completion rate |
| Outreach follow-ups | 10% | -5 per overdue contact |

Thresholds: 85+ green, 70-84 yellow, below 70 red.

### Automated Monitoring Rules

- **Deadline Enforcer:** 48h info → 24h attention → overdue urgent → overdue+blocks critical
- **Automation Staleness:** 1.5x expected interval = stale warning, 3x = failed urgent + Telegram alert
- **Ad Signals:** Scale/Hold/Optimize/Pause/Kill based on CPL, CTR, conversion rate, spend vs budget
- **Channel Health:** Platform-specific rules (email open rates, social posting frequency, content cadence, referral activity)
- **Anomaly Detection:** 7-day average comparison, >15% deviation flagged, >30% = attention severity
- **Gap Analysis:** Channels with no tasks, empty pipeline stages, overdue follow-ups, tool category gaps, budget overruns

### Insight Lifecycle

All monitoring generates `AIInsight` records with:
- Severity levels: info, attention, urgent, critical
- `why_it_matters` field explaining business impact
- `suggested_action` field with concrete next steps
- `fix_url` linking to the relevant page
- Resolve, dismiss, snooze, and investigate actions
- Deduplication: existing unresolved insights are updated rather than duplicated

---

## 8. Known Issues and Limitations

### Architectural Limitations

1. **Single-machine deployment.** Runs only on Phil's Mac Mini. No cloud deployment, no remote access (unless tunneled).
2. **Single-process SQLite.** No concurrent write safety beyond SQLAlchemy's connection-level locking. Not an issue for single-user but blocks scaling.
3. **No mobile optimization.** Desktop primary (1280px+). Sidebar collapses to icons at 1024px.
4. **No authentication.** Localhost access only — no login system. Partner views use token-based URLs.

### Integration Limitations

1. **Several integrations are "framework ready" but not actively pulling data.** Stripe, Meta Ads, Reddit Ads, Google Ads, SparkLoop, and Railway integrations have code but depend on API keys and/or post-launch data.
2. **No real-time webhooks.** All integrations are poll-based on intervals (4-6 hours). Events between polls are not captured until next refresh.
3. **Ad platforms not yet active.** Grindlab hasn't launched paid ads yet — the signal system and ad management are ready but contain no live data.

### Data Limitations

1. **Subscriber data is snapshot-based.** No real-time subscriber tracking until Stripe and ConvertKit webhooks are implemented.
2. **Lead scoring depends on subscriber events.** With limited event data pre-launch, scoring is minimal.
3. **Content performance data requires manual entry** for platforms without API integrations.

### Operational Notes

1. **Two disabled Launch Agents** (`com.philgiliam.scotty-autonomous`, `com.scotty.nightly`) — scripts missing from disk. Disabled 2026-03-08.
2. **Scotty Automation Master** only runs during the automation window (Friday 5 PM → Monday 8 AM) unless manually overridden.
3. **Budget auto-fill** only covers fixed subscriptions with hardcoded amounts (ConvertKit $79, Buffer $30, Instantly $97, Railway $5, X Premium $4). Variable costs require manual entry.
4. **AI features** require a valid `ANTHROPIC_API_KEY`. Without it, all 18 AI jobs produce no output, chat returns a fallback message, and content prep is skipped. The app remains fully functional otherwise.
5. **Daily backup script** pushes to GitHub using `gh auth token`. If the token expires or `gh` is not authenticated, pushes silently fail and retry next run.

---

## 9. Dependencies

### Python Packages (requirements.txt)

```
fastapi
uvicorn[standard]
sqlalchemy
jinja2
httpx
apscheduler
anthropic
python-multipart
```

### CDN Dependencies

- Tailwind CSS
- HTMX
- Chart.js
- Sortable.js
- Inter font (Google Fonts)

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Anthropic API | AI features (chat, insights, content prep) | No (graceful fallback) |
| Healthchecks.io | Dead man's switch monitoring | No |
| Telegram Bot API | Alert delivery | No |
| ConvertKit API | Email subscriber data | No |
| Instantly API | Cold email metrics | No |
| Google Analytics 4 | Website analytics | No |
| Buffer API | Social media management | No |
| YouTube Data API | Subscriber count | No |
| GitHub | Code backup via `gh` CLI | No |

No external service is required for MCC to run. All degrade gracefully.
