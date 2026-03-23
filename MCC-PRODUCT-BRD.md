# Marketing Command Center (MCC) — Product BRD

**Document Version:** 2.0
**Date:** 2026-03-08
**Author:** Phil Gilliam
**Purpose:** Comprehensive reference for MCC as a standalone product. Written so a reader with no codebase access can understand exactly what exists, what works, and what needs to be built.

---

## 1. Product Vision

### What MCC Is

MCC is a self-hosted marketing execution platform built for solo operators and small marketing teams (1-3 people). It consolidates channels, tasks, automations, metrics, content, outreach, ads, and budget into one system — then adds an AI-powered "execution guarantee" layer that monitors for anomalies, missed deadlines, stale automations, and compounding failures before they become problems.

### Who It's For

- **Primary:** Solo marketing operators running 10+ channels, 15+ tools, and 30+ tasks for a product launch
- **Secondary:** Small marketing teams (2-3 people) who need a shared execution dashboard without enterprise overhead
- **Anti-target:** Agencies, large teams, or anyone who wants a SaaS they don't self-host (yet)

### What Problem It Solves

A one-person marketing operation across 14+ channels, 17+ tools, 10+ automations, and 40+ tasks has too many moving parts. Things fall through the cracks — stale automations go unnoticed, follow-ups are missed, content pipelines stall, deadlines compound, and there is no single place to see what's broken, what's working, and what needs attention next.

Existing tools (Notion, Asana, Monday, HubSpot) either:
- Are generic project management tools that don't understand marketing execution
- Are expensive marketing suites designed for teams of 10+
- Don't connect automations, metrics, content, and tasks into a unified health picture

MCC fills the gap: a marketing-specific command center with built-in intelligence.

### Long-Term Vision

MCC is designed as a **reusable launch platform for multiple products**. The data model is already project-scoped — every entity (channel, task, metric, automation, content piece, etc.) belongs to a project. After launching Grindlab (poker study SaaS, April 1 2026), the same MCC instance should support launching a second, third, and Nth product using launch templates and shared knowledge base.

The eventual goal: a portable, cloud-deployable platform that any solo operator can spin up for their own product launches.

### First Project

**Grindlab** — a poker study SaaS at grindlab.ai. Launch date: April 1, 2026.
- 14 marketing channels (8 live, 6 planned)
- 17+ tools in the tech stack
- 40+ tasks with dependency chains
- 10+ automations
- 6 email sequences (3 live, 3 not yet built)
- 4 competitors tracked
- 10 outreach contacts

---

## 2. Current State Audit

### 2.1 Operations Views

| Feature | Route | Status | Notes |
|---------|-------|--------|-------|
| Dashboard | `/` | **Fully working** | Execution score (0-100), channel health grid, urgent items, AI insights panel, launch countdown timer, morning brief, MRR tracking, budget summary widget, Scotty tool health |
| Daily Ops | `/daily` | **Fully working** | Morning briefing with today's tasks, automation status, overnight alerts |
| Calendar | `/calendar` | **Fully working** | Unified marketing calendar aggregating content, emails, ads, events |
| Roadmap | `/roadmap` | **Fully working** | Timeline view with tasks, due dates, dependency tracking |
| Weekly Review | `/weekly` | **Fully working** | Full metrics review with task velocity, channel performance |

### 2.2 Execution Views

| Feature | Route | Status | Notes |
|---------|-------|--------|-------|
| Tasks | `/tasks` | **Fully working** | Kanban board with 8 columns (backlog, this_week, in_progress, blocked, done, archived, monitoring, recurring). Drag-and-drop via Sortable.js. Create/edit modals, dependency fields, recurring task auto-generation, task archiving with completion dates, checklist items per task |
| Content Pipeline | `/pipelines/content` | **Fully working** | Content pipeline kanban (concept → scripted → filmed → with_editor → edited → scheduled → published). AI content prep generates drafts to Approval Queue |
| Outreach Pipeline | `/pipelines/outreach` | **Fully working** | Influencer/ambassador/affiliate pipeline with follow-up tracking, auto-drafted follow-ups and decline checks via Approval Queue |
| Ads | `/ads` | **Framework working, no live data** | Campaign management with automated signal system (scale/hold/optimize/pause/kill). Signal calculator runs on schedule. No active ad campaigns pre-launch |
| Approval Queue | `/queue` | **Fully working** | Human-in-the-loop queue for AI-generated content drafts, outreach follow-ups, decline checks, check-in reminders. Pending/approved/edited/skipped/rejected states |

### 2.3 Intelligence Views

| Feature | Route | Status | Notes |
|---------|-------|--------|-------|
| What's Working | `/whats-working` | **Fully working** | Messaging analysis, content performance tracking |
| Subscribers | `/subscribers` | **Partially working** | Funnel visualization, subscriber snapshots by stage. Snapshot-based — no real-time tracking until Stripe webhooks are live |
| Retention | `/retention` | **Framework only** | Retention segments view. Requires post-launch subscriber event data |
| Feedback | `/feedback` | **Fully working** | Customer feedback with testimonials, sentiment, NPS |
| Competitors | `/competitors` | **Fully working** | 4 competitor profiles with pricing, strengths, weaknesses, key channels. CompetitorUpdate log for tracking changes |
| Intelligence | `/intelligence` | **Fully working** | Three tabs: channel discovery, tool discovery, landscape monitoring. Items have fit scores and urgency levels |
| Website | `/website` | **Fully working** | Website intelligence with scheduled weekly analysis job |
| Discovery | `/discovery` | **Fully working** | Discovery/exploration tools |

### 2.4 System Views

| Feature | Route | Status | Notes |
|---------|-------|--------|-------|
| Channels | `/channels` | **Fully working** | Channel CRUD + detail views with metric charts. 14 channels seeded (8 live, 6 planned) |
| Automations | `/automations` | **Fully working** | Automation registry with health indicators, staleness detection, hosting location, health check method |
| Tech Stack | `/techstack` | **Fully working** | Tool management with gap/redundancy detection. 17+ tools seeded with monthly costs, billing cycles, API integration flags |
| Budget | `/budget` | **Fully working** | Budget planner with line items, monthly entries (budgeted vs actual), auto-fill for fixed subscriptions, allocation by category, expense tracking |
| Strategy | `/strategy` | **Fully working** | Strategy document builder with 7 sections (product, customer, competitors, messaging, voice, pillars, budget). AI conversation per section |
| Settings | `/settings` | **Fully working** | API key configuration, integration status display, threshold settings |
| Brand | `/brand` | **Fully working** | Brand colors, fonts, platform profiles, brand guidelines (voice rules, banned words, tone, content mix), brand assets |
| Templates | `/templates` | **Fully working** | Launch templates with template tasks. Templates store relative day offsets and can be applied to new projects |
| Experiments | `/experiments` | **Fully working** | A/B test tracking with hypothesis, variants, success metrics, winner determination, knowledge base linking |

### 2.5 Global Features

| Feature | Route | Status | Notes |
|---------|-------|--------|-------|
| AI Chat | `/chat` | **Fully working** | Slide-out panel with full conversation history. 16+ tool definitions (get_channel_metrics, create_task, update_task, record_metric, get_ad_campaigns, get_execution_score, track_entity, etc.). Page-context awareness — chat knows which view user is on |
| Knowledge Base | `/knowledge` | **Fully working** | Cross-project knowledge entries (lessons, tool decisions, playbooks, benchmarks, patterns). Can be AI-generated or manual |
| Search | `/search` | **Fully working** | Global search across entity types |
| Wizard | `/wizard` | **Fully working** | Project setup wizard |
| Partner View | `/partner` | **Fully working** | Shareable read-only dashboards with token-based URL access. Preset configurations, custom configs, banner text |

### 2.6 API Endpoints

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/metrics/record` | POST | **Fully working** | External scripts push metrics directly to MCC |
| `/api/automations/heartbeat` | POST | **Fully working** | External scripts report automation execution health |
| `/api/tools/heartbeat` | POST | **Fully working** | Scotty/autonomous tool health reporting. API key authenticated |
| `/api/tools/metrics` | POST | **Fully working** | Autonomous tool metric reporting. API key authenticated |
| `/api/tools/*` | Various | **Fully working** | Tool management, registration, and status endpoints |

---

## 3. Architecture

### 3.1 Tech Stack

| Component | Technology | Version/Details |
|-----------|-----------|----------------|
| Language | Python | 3.14 |
| Web Framework | FastAPI | Server-rendered HTML, not REST API |
| Template Engine | Jinja2 | All HTML server-rendered |
| Frontend Interactivity | HTMX | Partial page updates, no SPA |
| CSS | Tailwind CSS | CDN, not compiled |
| Database | SQLite | Via SQLAlchemy ORM, file: `data/mcc.db` |
| Scheduler | APScheduler | BackgroundScheduler, in-process |
| AI Provider | Anthropic API | Claude Sonnet 4, direct httpx calls (not SDK) |
| HTTP Client | httpx | Async, used for all external API calls |
| Charts | Chart.js | CDN |
| Drag/Drop | Sortable.js | CDN |
| Fonts | Inter | Google Fonts CDN |

### 3.2 Architectural Constraints

1. **Server-rendered HTML + HTMX.** No React, Vue, or SPA frameworks.
2. **SQLite only.** No Postgres, Redis, or other databases.
3. **Single Python process.** No Docker, no multi-process workers.
4. **Graceful degradation.** Missing API keys = feature skipped, never crash.
5. **Dark theme.** Fixed palette: bg `#0F0F23`, cards `#1A1A2E`, accent `#E94560`, text `#F0F0F0`.

### 3.3 Data Model Summary

**42 SQLAlchemy models** across these domains:

**Core:**
- `Project` — top-level entity, all other models FK to it
- `Channel` (14 types: email, social, paid_ads, referral, content, community, cold_outreach, seo, partnerships)
- `Tool` (13 categories: email_marketing, cold_outreach, analytics, social_mgmt, ads_platform, content_production, automation, referral, payments, hosting, ai_llm, dev_tools, scraping)

**Execution:**
- `Task` (8 statuses: backlog, this_week, in_progress, blocked, done, archived, monitoring, recurring)
- `ChecklistItem` — subtasks within a task
- `Automation` (types: cron_job, email_sequence, webhook_pipeline, scheduled_post, referral_program, ad_campaign)
- `EmailSequence` (types: nurture_drip, broadcast, transactional, triggered, onboarding, retention, win_back)
- `AdCampaign` (platforms: meta, reddit, google, youtube, x_twitter, tiktok; signals: scale/hold/optimize/pause/kill)
- `ContentPiece` (7-stage pipeline: concept → scripted → filmed → with_editor → edited → scheduled → published)
- `ContentTag` — multi-dimensional tagging (hook_type, topic, pillar, tone, format, cta_type, audience)
- `OutreachContact` (8 statuses: identified → contacted → responded → in_conversation → committed → active; also declined, ghosted)
- `ApprovalQueueItem` (types: outreach_followup, decline_check, checkin, content_draft, content_suggestion, ai_recommendation, discovered_prospect)

**Intelligence:**
- `Metric` + `MetricSnapshot` — time-series metric storage per channel
- `AIInsight` — all monitoring output (10 types: anomaly, deadline_warning, dependency_risk, stale_automation, ad_signal, suggestion, trend, gap_analysis, weekly_digest, bottleneck; 4 severities: info, attention, urgent, critical)
- `PerformanceScore` — cross-entity performance tracking
- `Experiment` — A/B test tracking
- `LeadScore` — subscriber scoring with tier system (hot/warm/cool/cold)
- `CustomerFeedback` — testimonials, feature requests, complaints, NPS
- `IntelligenceItem` — channel/tool discovery and landscape monitoring
- `Competitor` + `CompetitorUpdate` — competitive intelligence
- `KnowledgeEntry` — cross-project knowledge base (lessons, decisions, playbooks, benchmarks, patterns)

**Subscribers:**
- `SubscriberSnapshot` — point-in-time subscriber counts by stage
- `SubscriberEvent` — individual subscriber lifecycle events
- `MonthlyRevenue` — MRR tracking

**Financial:**
- `BudgetAllocation` — planned monthly budgets by category
- `BudgetExpense` — actual expenses
- `BudgetLineItem` + `BudgetMonthEntry` — line-item budgeting with monthly granularity

**Strategy:**
- `ProjectStrategy` — 7 sections (product, customer, competitors, messaging, voice, pillars, budget)
- `BrandColor`, `BrandFont`, `BrandAsset`, `PlatformProfile`, `BrandGuidelines`
- `LaunchTemplate` + `TemplateTask` — reusable launch templates

**System:**
- `ChatConversation` + `ChatMessage` — AI chat history with tool call/result storage
- `PartnerView` — shareable read-only dashboards
- `AutonomousTool` — external tool registration (Scotty)
- `ToolMetricLog` + `ToolAlert` — tool health tracking
- `OnboardingMilestone` + `OnboardingProgress` — user onboarding tracking
- `MorningBrief` — cached morning briefings

**All models are project-scoped** (FK to Project) except:
- `KnowledgeEntry` (optional project_id — can be global)
- `ChatConversation` / `ChatMessage`
- `LaunchTemplate` / `TemplateTask`

### 3.4 Route Architecture

**33 route modules** registered in `app/main.py`:

```
dashboard, channels, metrics, subscribers, ai, tasks, roadmap,
daily, calendar_view, weekly, automations, pipelines, feedback,
ads, techstack, budget, experiments, whats_working, api,
chat, strategy, knowledge, competitors, partner, retention,
wizard, search, tools_api, tools_mgmt, settings, checklist,
templates, brand, track, strategy_export, discovery, intelligence,
website, queue
```

### 3.5 Process Model

- Runs as a **macOS Launch Agent** (`com.grindlab.mcc`) with `KeepAlive: true`
- Auto-restarts on crash
- Logs to `~/marketing-command-center/logs/mcc.log` and `mcc_error.log`
- Port 5050 (reserved, localhost only)
- Single `uvicorn` process
- APScheduler runs in-process as a `BackgroundScheduler`
- SQLite database at `data/mcc.db` with 14-day rolling backups

### 3.6 Current Deployment

- **Host:** Phil's Mac Mini (Phils-Mac-mini.local), macOS
- **Access:** `localhost:5050` only — no remote access, no auth
- **Backup:** Daily at 3 AM — database copy (14-day retention) + git commit + push to GitHub
- **Monitoring:** Healthchecks.io dead man's switch (30-min pings) + Telegram alerts for critical events

---

## 4. Integrations

### 4.1 Pull Integrations (MCC fetches data from external APIs)

All integrations inherit from `IntegrationBase` which provides:
- `is_configured()` — checks if required env vars are set
- `connect()` → `fetch_metrics()` → stores `MetricReading` objects
- Exponential backoff retry (3 attempts, rate-limit handling via 429 detection)
- Consecutive failure tracking → health status (healthy at 0, warning at 1, critical at 3+)
- Graceful fallback: missing API key = skip, not crash
- Default timeout: 10s per request

| Integration | Class | Data Pulled | Refresh | Env Vars | Status |
|------------|-------|------------|---------|----------|--------|
| ConvertKit | `ConvertKitIntegration` | Subscribers, new today, by tag, sequence open/click rates | 4h | `CONVERTKIT_API_SECRET` | **Live, pulling data** |
| Instantly | `InstantlyIntegration` | Sent, opens, replies, bounces | 6h | `INSTANTLY_API_KEY` | **Live, pulling data** |
| GA4 | `GA4Integration` | Pageviews, sessions, conversions, sources | 6h | `GA4_CREDENTIALS_PATH` + `GA4_PROPERTY_ID` | **Live, pulling data** |
| Buffer | `BufferIntegration` | Queue count, sent posts, engagement, social metrics (GraphQL API) | 4h | `BUFFER_ACCESS_TOKEN` | **Live, pulling data** |
| Stripe | `StripeIntegration` | MRR, trials, conversion rate, churn | 4h | `STRIPE_API_KEY` | **Framework ready** — no live data pre-launch |
| Meta Ads | `MetaAdsIntegration` | Spend, impressions, clicks, CTR, CPL, ROAS | 6h | `META_ADS_ACCESS_TOKEN` | **Framework ready** — no ad campaigns yet |
| Reddit Ads | `RedditAdsIntegration` | Spend, impressions, clicks, CTR, CPL | 6h | `REDDIT_ADS_TOKEN` | **Framework ready** — no ad campaigns yet |
| Google Ads | `GoogleAdsIntegration` | Spend, impressions, clicks, CTR, video views | 6h | `GOOGLE_ADS_CREDENTIALS` | **Framework ready** — no ad campaigns yet |

### 4.2 Additional Data Sources (Not IntegrationBase subclasses)

| Source | Method | Env Vars | Refresh | Status |
|--------|--------|----------|---------|--------|
| YouTube Data API | Direct API call in `auto_metrics.py` (social_metrics_job) | `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID` | 6h | **Live, pulling subscriber count** |
| Reddit karma | Public JSON endpoint, no auth | `REDDIT_USERNAME` | 6h | **Live, pulling karma** |
| Hunter.io | Contact enrichment on demand | `HUNTER_API_KEY` | On-demand | **Configured, used on-demand** |
| SparkLoop | Referral data | `SPARKLOOP_API_KEY` | — | **Framework ready, not started** |
| Railway | Workflow health | `RAILWAY_API_KEY` | — | **Framework ready, not started** |

### 4.3 Push APIs (External systems push data to MCC)

| Endpoint | Purpose | Auth Method | Status |
|----------|---------|-------------|--------|
| `POST /api/metrics/record` | Scotty/cron scripts push metrics | API key header (`X-Api-Key`) | **Live, receiving data** |
| `POST /api/automations/heartbeat` | Scotty reports automation health | API key header | **Live, receiving data** |
| `POST /api/tools/heartbeat` | Scotty sends health pings | API key header | **Live, receiving pings** |
| `POST /api/tools/metrics` | Scotty reports tool metrics (e.g. backup_size_kb) | API key header | **Live, receiving data** |

### 4.4 Alert System (3 Levels)

| Level | Method | Status | Details |
|-------|--------|--------|---------|
| Level 1: Dashboard | AIInsight records displayed in dashboard urgent items panel | **Always active** | All monitoring jobs write AIInsight records |
| Level 2: Telegram | Bot messages for critical/warning events | **Requires config** | Needs `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`. Uses urllib (no SDK) |
| Level 3: Healthchecks.io | External dead man's switch — if Mac Mini stops pinging, external alert fires | **Live** | Heartbeat every 30 min via cron. Needs `HEALTHCHECKS_PING_URL` |

### 4.5 AI Engine

- **Provider:** Anthropic API (Claude Sonnet 4, model `claude-sonnet-4-20250514`)
- **Implementation:** Direct httpx calls to `https://api.anthropic.com/v1/messages` (not using the Anthropic Python SDK)
- **Max tokens:** 4096
- **System prompt:** Grindlab-focused, action-oriented personality
- **Tool use:** 16+ tool definitions for chat (get_channel_metrics, get_task_list, create_task, update_task, record_metric, get_ad_campaigns, get_execution_score, track_entity, stop_tracking_entity, get_weekly_summary, etc.)
- **Page context:** Chat API receives which view the user is on
- **Graceful degradation:** Without `ANTHROPIC_API_KEY`, all AI features return fallback messages. App remains fully functional.
- **Cost estimate:** ~$12/month at current usage

### 4.6 All Environment Variables

```
# AI
ANTHROPIC_API_KEY

# Integrations
CONVERTKIT_API_SECRET
INSTANTLY_API_KEY
GA4_CREDENTIALS_PATH (or GOOGLE_ANALYTICS_KEY_FILE)
GA4_PROPERTY_ID
BUFFER_ACCESS_TOKEN
STRIPE_API_KEY
META_ADS_ACCESS_TOKEN
REDDIT_ADS_TOKEN
GOOGLE_ADS_CREDENTIALS
SPARKLOOP_API_KEY
RAILWAY_API_KEY
YOUTUBE_API_KEY
YOUTUBE_CHANNEL_ID
HUNTER_API_KEY
REDDIT_USERNAME

# Alerts & Monitoring
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
HEALTHCHECKS_PING_URL

# System
LAUNCH_COMMAND_DB_PATH (default: data/mcc.db)
LAUNCH_COMMAND_PORT (default: 5050)
```

---

## 5. Automation Engine

### 5.1 In-Process APScheduler Jobs (26 total)

#### Integration Refresh Jobs (8)

| # | Job ID | Function | Schedule | What It Does |
|---|--------|----------|----------|-------------|
| 1 | `integration_ConvertKit` | `run_integration_sync(ConvertKitIntegration)` | Every 4h | Pull subscriber counts, tag data, sequence metrics |
| 2 | `integration_Instantly` | `run_integration_sync(InstantlyIntegration)` | Every 6h | Pull send/open/reply/bounce metrics |
| 3 | `integration_GA4` | `run_integration_sync(GA4Integration)` | Every 6h | Pull pageviews, sessions, conversions |
| 4 | `integration_Buffer` | `run_integration_sync(BufferIntegration)` | Every 4h | Pull queue count, social metrics (GraphQL) |
| 5 | `integration_Stripe` | `run_integration_sync(StripeIntegration)` | Every 4h | Pull MRR, trials, churn (post-launch only) |
| 6 | `integration_MetaAds` | `run_integration_sync(MetaAdsIntegration)` | Every 6h | Pull ad spend, impressions, clicks |
| 7 | `integration_RedditAds` | `run_integration_sync(RedditAdsIntegration)` | Every 6h | Pull ad spend, impressions, clicks |
| 8 | `integration_GoogleAds` | `run_integration_sync(GoogleAdsIntegration)` | Every 6h | Pull ad spend, impressions, clicks |

**Note:** Only configured integrations are registered. Unconfigured integrations are skipped at startup.

#### AI Monitoring Jobs (18)

| # | Job ID | Function | Schedule | What It Does | Producing Output? |
|---|--------|----------|----------|-------------|-------------------|
| 9 | `ai_deadline_enforcer` | `run_deadline_enforcer` | Every 6h | Checks tasks: 48h info, 24h warning, overdue alert, dependency chain analysis. Creates/updates AIInsight records | **Yes** — tasks with due dates get monitored |
| 10 | `ai_anomaly_detector` | `run_anomaly_detector` | Daily 6 AM | Compares metrics to 7-day avg, flags >15% deviations, >30% = attention severity | **Yes** — when sufficient metric history exists |
| 11 | `ai_automation_health` | `run_automation_health` | Every 4h | Checks all automations for staleness (1.5x expected = stale, 3x = failed). Telegram alerts for failures | **Yes** — active automations are monitored |
| 12 | `ai_ad_signal` | `run_ad_signal_calculator` | Every 6h | Recalculates campaign signals (scale/hold/optimize/pause/kill) based on CPL, CTR, conversions | **Not yet** — no active ad campaigns |
| 13 | `ai_gap_analyzer` | `run_gap_analyzer` | Weekly Sun 6 AM | Checks: channels with no tasks, empty pipeline stages, overdue follow-ups, tool category gaps, budget overruns | **Yes** — structural analysis runs regardless |
| 14 | `ai_weekly_digest` | `run_weekly_digest` | Weekly Sun 7 AM | Full project summary with execution score, task/content/channel/automation stats | **Yes** — weekly AIInsight digest |
| 15 | `ai_outreach_followup` | `run_outreach_followup` | Daily 8 AM | Flags overdue contact follow-ups, updates/creates AIInsight with dedup | **Yes** — when contacts have follow-up dates |
| 16 | `ai_content_pipeline` | `run_content_pipeline_check` | Daily 9 AM | Checks content published vs weekly target (3/week). Creates AIInsight if behind | **Yes** — tracks content cadence |
| 17 | `ai_lead_scoring` | `run_lead_scoring` | Weekly Sun 5 AM | Scores leads based on subscriber events with decay for inactivity. Tiers: hot/warm/cool/cold | **Minimal** — limited subscriber event data pre-launch |
| 18 | `ai_channel_intelligence` | `run_channel_intelligence` | Weekly Sun 6:30 AM | Channel performance digest, WoW comparisons, stale nudges, Telegram summary | **Yes** — weekly channel health report |
| 19 | `ai_channel_metric_monitor` | `run_channel_metric_monitor` | Every 6h | Checks for >20% drops in primary channel metrics. 12h dedup window | **Yes** — monitors all live channels |
| 20 | `status_export` | `status_export_job` | Daily 6 AM | Writes `MCC-STATUS.md` to `~/clawd/projects/grindlab/` for external systems | **Yes** — file export |
| 21 | `strategy_export` | `strategy_export_job` | Weekly Sun 6 AM | Exports strategy document to external file | **Yes** — file export |
| 22 | `website_intelligence` | `website_intelligence_job` | Weekly Sun 7:30 AM | Website analysis job | **Yes** |
| 23 | `morning_brief` | `morning_brief_job` | Daily 7 AM | Generates morning briefing for dashboard | **Yes** — populates MorningBrief model |
| 24 | `social_metrics` | `social_metrics_job` | Every 6h | YouTube subscriber count, Reddit karma, Buffer social metrics | **Yes** — live data |
| 25 | `outreach_workflow` | `run_outreach_workflow` | Daily 8:30 AM | Scans contacts, auto-drafts follow-ups, surfaces decline checks and check-ins in Approval Queue | **Yes** — creates ApprovalQueueItems |
| 26 | `content_prep` | `content_prep_job` | Weekly Sat 9 AM | AI generates 5-7 draft social posts based on content pillars, places in Approval Queue. Skips if 5+ already pending | **Yes** — requires ANTHROPIC_API_KEY |

### 5.2 External Cron Jobs (MCC-owned)

| Schedule | Script | What It Does | Status |
|----------|--------|-------------|--------|
| 3 AM daily | `scripts/daily_backup.sh` | SQLite database backup (14-day retention), git add + commit, push to GitHub via `gh auth token`, heartbeat to MCC via tools API | **Live and working** |
| Every 30 min | `scripts/heartbeat_ping.sh` | Pings Healthchecks.io dead man's switch. Also pings MCC tools API if running. If this stops, external alert fires | **Live and working** |

### 5.3 External Cron Jobs (Clawd/Scotty, separate system)

These run from `~/clawd/` and push data to MCC via the API endpoints.

| Schedule | Script | What It Does | Status |
|----------|--------|-------------|--------|
| 1 AM daily | `backup-system.sh` | Clawd system backup | **Running** |
| 7:00 AM daily | `reddit_daily_brief.py` | Scans subreddits for Grindlab-relevant posts | **Running** (log: 5.9h ago) |
| 7:05 AM daily | `pipeline_health_check.py` | Validates marketing pipeline status | **Running** (log: 5.8h ago) |
| 7:15 AM daily | `youtube_comment_targets.py` | Finds YouTube videos to engage with | **Running** (log: 5.7h ago) |
| 7:20 AM daily | `forum_comment_targets.py` | Finds forum threads for outreach | **Running** (log: 5.6h ago) |
| Every 4 hours | `milestone_alerts.py` | Checks project milestones and alerts | **Running** (log: 56m ago) |
| Monday 8 AM | `outreach_discovery.py` | Discovers new outreach opportunities | **Running** (log: 1.1d ago — stale but weekly) |
| Sunday 8 AM | `weekly_metrics_rollup.py` | Aggregates weekly performance data | **Running** (log: 4.9h ago) |
| Sunday 9 PM | `landscape_monitor.py` | Competitive/market landscape scan | **Running** |
| 7:25 AM daily | `grindlab-content-monitor.sh` | Daily content generation (migrated from OpenClaw) | **Running** |
| Mon/Thu 10 AM | `strategic-research.py` | Strategic research (migrated from OpenClaw) | **New** — log not yet created |
| 7:30 AM / 6 PM | `mcc-alert-bridge.py` | Morning + evening critical insight alerts | **New** — log not yet created |
| 8 AM daily | `cron-health-watchdog.py` | Stale log check across all cron jobs | **New** — log not yet created |
| 6 AM daily | `sync-system-status.py` | Infrastructure snapshot → SYSTEM-STATUS.md | **Running** |

### 5.4 Execution Guarantee System

#### Execution Score (0-100)

The core health metric. Calculated in real-time from 6 weighted components:

| Component | Weight | Scoring Logic |
|-----------|--------|--------------|
| Tasks on track | 25% | Start at 100. -5 per overdue task, -10 per launch-critical overdue task |
| Automations healthy | 20% | Start at 100. -15 per stale automation, -25 per failed automation |
| Channels healthy | 20% | Start at 100. -10 per warning channel, -20 per critical channel |
| Content pipeline | 15% | Published this week / weekly target (3). Capped at 100% |
| Recurring tasks done | 10% | Completion rate of recurring tasks due today or earlier |
| Outreach follow-ups | 10% | Start at 100. -5 per overdue contact follow-up |

**Thresholds:** 85+ = green, 70-84 = yellow, below 70 = red.

#### Monitoring Rules

- **Deadline Enforcer:** 48h → info, 24h → attention, overdue → urgent, overdue + blocks other tasks → critical
- **Automation Staleness:** 1.5x expected interval = stale (warning), 3x = failed (urgent + Telegram alert)
- **Ad Signals:** Scale/Hold/Optimize/Pause/Kill based on CPL, CTR, conversion rate, spend vs budget
- **Channel Health:** >20% WoW metric drop = attention alert + Telegram warning
- **Anomaly Detection:** 7-day average comparison, >15% deviation = info, >30% = attention
- **Gap Analysis:** Weekly structural check for orphan channels, empty pipeline stages, overdue follow-ups, tool category gaps, budget overruns

#### Insight Lifecycle

All monitoring generates `AIInsight` records with:
- 10 insight types (anomaly, deadline_warning, dependency_risk, stale_automation, ad_signal, suggestion, trend, gap_analysis, weekly_digest, bottleneck)
- 4 severity levels: info, attention, urgent, critical
- `why_it_matters` — business impact explanation
- `suggested_action` — concrete next steps
- `fix_url` — deep link to relevant page
- Actions: resolve, dismiss, snooze, investigate
- Deduplication: existing unresolved insights for the same source are updated rather than duplicated (checked by source_type + source_id + insight_type)

---

## 6. Scotty/Clawd Integration

### 6.1 What Scotty/Clawd Is

Scotty (also called Clawd) is a separate automation system running from `~/clawd/` on the same Mac Mini. It runs 9+ cron jobs that perform marketing research, outreach discovery, pipeline health checks, and competitive monitoring for Grindlab. It pushes data into MCC via the API endpoints.

### 6.2 How Data Flows

```
Scotty cron scripts (~/clawd/)
    │
    ├── POST /api/metrics/record ──────→ MCC Metric table
    ├── POST /api/automations/heartbeat → MCC Automation health
    ├── POST /api/tools/heartbeat ─────→ MCC AutonomousTool health
    └── POST /api/tools/metrics ───────→ MCC ToolMetricLog
```

- All push APIs are authenticated via `X-Api-Key` header
- The API key is stored in the `AutonomousTool` table (Scotty is registered as an autonomous tool)
- Scripts retrieve the API key by querying the MCC database directly (via Python import)

### 6.3 Alert Bridge

`mcc-alert-bridge.py` runs 2x daily (7:30 AM + 6 PM). It reads critical/urgent AIInsight records from MCC and bridges them to external notification channels (Telegram, potentially others).

### 6.4 Cron Health Watchdog

`cron-health-watchdog.py` runs daily at 8 AM. It checks all cron job log files for staleness — if any log hasn't been updated within its expected interval, it raises an alert. This catches silent cron failures.

### 6.5 System Status Sync

`sync-system-status.py` runs daily at 6 AM. It generates `SYSTEM-STATUS.md` with:
- Service health (port checks for MCC, OpenClaw Gateway, n8n, Scotty Dashboard)
- LaunchAgent status
- Crontab entries
- Log freshness for all Grindlab cron jobs
- MCC error log tail

### 6.6 Status Export (MCC → Scotty)

MCC's `status_export_job` runs daily at 6 AM and writes `MCC-STATUS.md` to `~/clawd/projects/grindlab/`. This gives Scotty scripts access to current MCC state without making API calls.

### 6.7 Scotty Automation Master

`com.scotty.automation` LaunchAgent runs `local-automation-master.sh` every 15 minutes. It only activates during the **automation window** (Friday 5 PM → Monday 8 AM) unless manually overridden via `~/clawd/memory/automation-schedule.json`. It runs improvement cycles and queues messages.

---

## 7. Known Issues and Gaps

### 7.1 Architectural Issues

| Issue | Severity | Details |
|-------|----------|---------|
| **Single-machine dependency** | Critical | Everything runs on one Mac Mini. Power loss, crash, or internet outage = total downtime. Only safety net is Healthchecks.io external monitoring |
| **No authentication** | High | Localhost only — no login, no RBAC. Partner views use token URLs but the main app is wide open. Blocks any cloud deployment |
| **No mobile optimization** | Medium | Desktop primary (1280px+). Sidebar collapses to icons at 1024px but below that is unusable. Can't manage MCC from a phone |
| **SQLite single-writer** | Low (for now) | No concurrent write safety beyond SQLAlchemy's connection-level locking. Not an issue for single user but blocks multi-user or multi-process |
| **CDN dependencies** | Medium | Tailwind, HTMX, Chart.js, Sortable.js, Inter font all loaded from CDNs. No internet = broken UI. No vendored fallbacks |

### 7.2 Integration Gaps

| Issue | Details |
|-------|---------|
| **4 "framework ready" integrations** | Stripe, Meta Ads, Reddit Ads, Google Ads have complete integration classes but no live data. Stripe needs post-launch subscribers; ad platforms need active campaigns |
| **No real-time webhooks** | All integrations are poll-based (4-6 hour intervals). Events between polls are missed until next refresh |
| **SparkLoop and Railway** | Config vars defined but no integration classes built |
| **Subscriber data is snapshot-based** | No real-time subscriber tracking. ConvertKit integration pulls totals, not individual events. Stripe webhooks needed for proper lifecycle tracking |

### 7.3 Data Issues

| Issue | Details |
|-------|---------|
| **Alert deduplication is inconsistent** | Deadline enforcer deduplicates by source_type + source_id + resolved_at/dismissed_at. Outreach follow-up deduplicates by title pattern matching (LIKE). Channel metric monitor uses 12h time window. No unified dedup strategy |
| **Lead scoring has minimal data** | Pre-launch, there are few subscriber events. Scoring is functional but produces minimal useful output |
| **Content performance requires manual entry** | For platforms without API integrations (YouTube video performance, Instagram, TikTok), performance data must be entered manually |
| **Budget auto-fill is hardcoded** | Only covers: ConvertKit $79, Buffer $30, Instantly $97, Railway $5, X Premium $4. Any new subscription requires code change |

### 7.4 Operational Issues

| Issue | Details |
|-------|---------|
| **Two disabled LaunchAgents** | `com.philgiliam.scotty-autonomous` and `com.scotty.nightly` — scripts missing from disk. Disabled 2026-03-08. Plists still exist |
| **Three new cron scripts have no logs yet** | `mcc-alert-bridge.py`, `cron-health-watchdog.py`, `strategic-research.py` — recently added, log files not yet created |
| **Stale log detection** | `influencer_enrichment.log` is 1.9d stale, `outreach_discovery.log` is 1.1d stale, `reddit_engaged.log` is 4.0d stale |
| **Daily backup uses `git add -A`** | Stages all changes including potentially sensitive files. Relies on `.gitignore` being correct |
| **GitHub push depends on `gh auth token`** | If token expires, pushes silently fail and retry next run. No alert for push failures |
| **AI features require ANTHROPIC_API_KEY** | Without it: 18 AI jobs produce no output, chat returns fallback, content prep skipped. Everything else works but the "intelligence" layer is gone |

### 7.5 Missing Features

| Feature | Impact |
|---------|--------|
| **No user authentication** | Blocks cloud deployment, multi-user support, and remote access |
| **No real-time notifications** | No WebSocket or SSE — dashboard must be manually refreshed to see new insights |
| **No data export** | No CSV/JSON export for metrics, tasks, or reports |
| **No undo/audit log** | No change history for edits. Deletes are permanent |
| **No backup verification** | Daily backup runs but no automated restore test |
| **No rate limiting on APIs** | Push endpoints have API key auth but no rate limiting |

---

## 8. Travel-Proof Requirements

### 8.1 Current State

Everything runs on Phil's Mac Mini at home. When traveling, there is:
- No access to MCC dashboard
- No way to run integrations
- External cron jobs stop
- Only Healthchecks.io monitors that the system went down

### 8.2 What Must Run 24/7

| System | Why | Migration Path |
|--------|-----|---------------|
| MCC web server | Dashboard access from anywhere | Railway deployment |
| APScheduler integration refresh jobs | Metrics must keep flowing | Move to Railway with MCC |
| APScheduler AI monitoring jobs | Execution guarantee must be continuous | Move to Railway with MCC |
| Daily backup | Data protection | GitHub Actions or Railway cron |
| Healthchecks.io ping | Dead man's switch | Railway health check endpoint |

### 8.3 What Can Tolerate Downtime

| System | Tolerance | Notes |
|--------|-----------|-------|
| Scotty cron jobs (9 scripts) | 1-2 days | Weekly jobs (rollup, landscape, outreach discovery) can miss a cycle. Daily jobs (reddit brief, pipeline health) are nice-to-have, not critical |
| Scotty Automation Master | Indefinite | Only runs weekends, improvement cycles are non-critical |
| n8n | Indefinite | Used for webhook pipelines, can be paused |
| Status export | Days | File export for Scotty, not critical path |

### 8.4 Railway Migration Requirements

1. **MCC core** — FastAPI + SQLite must work on Railway. SQLite on Railway uses ephemeral filesystem; need persistent volume or migrate to PostgreSQL
2. **APScheduler** — works in-process, no changes needed
3. **Environment variables** — all 20+ env vars must be configured in Railway
4. **Database persistence** — Railway volumes or switch to Railway's managed Postgres
5. **Authentication** — must add before exposing to internet
6. **HTTPS** — Railway provides this automatically
7. **Custom domain** — optional but nice for partner views

### 8.5 Starlink/Intermittent Connectivity Constraints

When traveling with Starlink:
- Connection drops every few minutes during some conditions
- Integration refresh jobs need retry logic (already built — 3 attempts with backoff)
- Webhook/push data from cron scripts will queue and fail if MCC is unreachable
- CDN dependencies (Tailwind, HTMX, etc.) will cause broken renders on slow connections
- **Mitigation:** Vendor all CDN assets locally before travel

---

## 9. Multi-Product Vision

### 9.1 Current Data Model Support

The data model is already project-scoped. Every major entity has a `project_id` FK:
- Channels, tasks, automations, content, ads, outreach, metrics, email sequences, competitors, budget, strategy, brand, subscribers, experiments, feedback, onboarding milestones, intelligence items, lead scores

**Global entities** (shared across projects):
- Knowledge base entries (optional project_id)
- Chat conversations
- Launch templates

### 9.2 What Works Today for Multi-Product

- Project CRUD exists via the wizard
- Seed data system (`seeds/grindlab.py`) can be replicated for new projects
- Launch templates can store task patterns with relative day offsets
- Knowledge base is designed for cross-project learning
- All views filter by project_id

### 9.3 What Needs to Change

| Area | Current State | Needed |
|------|--------------|--------|
| **Project switching** | Hardcoded to "grindlab" slug in many AI jobs (`_get_project(db)` always queries `slug="grindlab"`) | Add project switcher in UI, pass project_id through all jobs |
| **Seed data** | `seeds/grindlab.py` is Grindlab-specific | Extract generic seed template; project-specific seeds become optional |
| **Launch templates** | Model exists, template tasks have relative days | Need UI flow: "New project from template" that applies template tasks with date offsets |
| **Integrations** | Not project-scoped — single set of API keys | Need per-project integration configs if running multiple products with different ConvertKit accounts, etc. |
| **Cron jobs** | Scotty scripts are Grindlab-specific | Need project-parameterized scripts or generic MCC-internal equivalents |
| **Budget** | Auto-fill amounts are hardcoded | Need per-project budget templates |
| **Morning brief** | Grindlab-specific | Need project-scoped briefs |
| **Dashboard** | Shows one project | Need project selector or multi-project dashboard |

### 9.4 Reusable Launch Template System

The template system (`LaunchTemplate` + `TemplateTask`) supports:
- Template name and description
- Template tasks with: title, description, relative_day (offset from launch date), priority, assigned_role, channel_type, checklist_items, dependencies

**To make it production-ready:**
1. Add "Apply Template" action that creates tasks with actual dates (launch_date + relative_day)
2. Add template channels and template automations (not just tasks)
3. Allow saving current project's setup as a new template
4. Support template versioning

---

## 10. Dependencies and Costs

### 10.1 Fixed Monthly Costs (Current)

| Service | Purpose | Monthly Cost |
|---------|---------|-------------|
| ConvertKit | Email marketing | $79 |
| Instantly | Cold email outreach | $97 |
| Buffer | Social media scheduling | $30 |
| X Premium | Twitter/X features | $4 |
| Railway | Grindlab hosting | $5 |
| Anthropic API | AI features (Claude Sonnet) | ~$12 |
| **Total Fixed** | | **~$227/mo** |

### 10.2 Free/Included Services

| Service | Purpose | Cost |
|---------|---------|------|
| Healthchecks.io | Dead man's switch | Free tier |
| Telegram Bot API | Alert delivery | Free |
| YouTube Data API | Subscriber count | Free tier |
| Reddit JSON | Karma scraping | Free (public endpoint) |
| Google Analytics 4 | Website analytics | Free |
| GitHub | Code backup | Free (included plan) |
| Hunter.io | Contact enrichment | Free tier / pay-per-use |
| Vercel | Grindlab frontend hosting | Free tier |
| Supabase | Grindlab backend | Free tier |

### 10.3 Variable/Usage-Based Costs

| Service | Purpose | Estimated Cost |
|---------|---------|---------------|
| Anthropic API | Scales with chat usage and content prep | $8-20/mo depending on usage |
| Meta Ads | Paid advertising (post-launch) | Budget TBD |
| Reddit Ads | Paid advertising (post-launch) | Budget TBD |
| Google Ads | Paid advertising (post-launch) | Budget TBD |
| Hunter.io | Contact enrichment (usage-based) | $0-49/mo |

### 10.4 Future Costs (If Cloud-Deployed)

| Service | Purpose | Estimated Cost |
|---------|---------|---------------|
| Railway (MCC hosting) | Cloud deployment | $5-20/mo |
| Railway Postgres | Database (if migrated from SQLite) | $5-10/mo |
| Custom domain | mcc.grindlab.ai or similar | $12/yr |

### 10.5 Python Dependencies

```
fastapi
uvicorn[standard]
sqlalchemy
jinja2
httpx
apscheduler
anthropic
python-multipart
python-dotenv (loaded in config.py)
```

### 10.6 CDN Dependencies

| Library | Purpose | Fallback Available? |
|---------|---------|-------------------|
| Tailwind CSS | Styling | No — UI breaks without it |
| HTMX | Frontend interactivity | No — interactions break without it |
| Chart.js | Metric charts | Partial — data displays as text |
| Sortable.js | Kanban drag-and-drop | Partial — boards work but no drag |
| Inter font | Typography | Yes — falls back to system font |

---

## Appendix A: File Structure

```
marketing-command-center/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, router registration, startup/shutdown
│   ├── config.py             # Environment variable loading
│   ├── database.py           # SQLAlchemy engine, session, Base
│   ├── models.py             # 42 SQLAlchemy models + 30+ enums
│   ├── scheduler.py          # APScheduler config, 26 job registrations
│   ├── alerts.py             # Telegram + Healthchecks.io alert system
│   ├── content_prep.py       # AI content draft generation
│   ├── outreach_workflow.py  # Auto follow-up drafting
│   ├── status_export.py      # Daily MCC-STATUS.md export
│   ├── ai/
│   │   ├── engine.py         # Anthropic API wrapper
│   │   ├── jobs.py           # 11 AI monitoring job functions
│   │   └── tools.py          # 16+ chat tool definitions and execution
│   ├── integrations/
│   │   ├── base.py           # IntegrationBase ABC
│   │   ├── engine.py         # run_integration_sync wrapper
│   │   ├── convertkit.py
│   │   ├── instantly.py
│   │   ├── ga4.py
│   │   ├── ga4_analytics.py
│   │   ├── buffer.py
│   │   ├── stripe_integration.py
│   │   ├── ad_platforms.py   # Meta, Reddit, Google Ads
│   │   └── auto_metrics.py   # YouTube, Reddit karma, social metrics
│   ├── routes/               # 33+ route modules
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # CSS, JS, images
├── data/
│   ├── mcc.db                # SQLite database
│   └── backups/              # Rolling 14-day DB backups
├── seeds/
│   └── grindlab.py           # Grindlab project seed data
├── scripts/
│   ├── daily_backup.sh       # Cron: 3 AM daily
│   └── heartbeat_ping.sh     # Cron: every 30 min
├── credentials/              # GA4 service account JSON
├── logs/
│   ├── mcc.log
│   └── mcc_error.log
├── manage.py                 # CLI management commands
├── run.py                    # Dev server launcher
├── requirements.txt
├── CLAUDE.md                 # Project instructions for Claude Code
├── MCC-COMPLETE-SPEC.md      # Full technical specification
├── MCC-BRD.md                # Initial BRD (v1)
├── MCC-PRODUCT-BRD.md        # This document (v2)
├── SCOTTY-AUTOMATION-REFERENCE.md
├── SYSTEM-STATUS.md          # Auto-generated infrastructure snapshot
└── venv/                     # Python virtual environment
```

---

## Appendix B: Launch Agent Configuration

```xml
<!-- ~/Library/LaunchAgents/com.grindlab.mcc.plist -->
Label: com.grindlab.mcc
Program: uvicorn app.main:app --host 0.0.0.0 --port 5050
WorkingDirectory: ~/marketing-command-center
KeepAlive: true
RunAtLoad: true
StandardOutPath: ~/marketing-command-center/logs/mcc.log
StandardErrorPath: ~/marketing-command-center/logs/mcc_error.log
```

---

*This BRD was generated from a full codebase audit on 2026-03-08. It reflects the actual state of the code, not aspirational features.*
