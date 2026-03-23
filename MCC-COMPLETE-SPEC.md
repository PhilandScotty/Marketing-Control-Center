# MARKETING COMMAND CENTER — COMPLETE TECHNICAL SPECIFICATION

**Version:** Final (consolidated v2-v5)  
**Build Target:** Claude Code on Mac Mini (Python 3.14, macOS)  
**First Project:** Grindlab (poker study SaaS, grindlab.ai)  
**Operator:** Phil Gilliam (solo marketing operator)

---

## 1. WHAT THIS IS

Marketing Command Center (MCC) is a local desktop marketing execution platform that guarantees nothing falls through the cracks for a one-person marketing operation. It is NOT a dashboard — it is an execution guarantee system with AI enforcement.

It tracks every channel, tool, automation, task, metric, deadline, dependency, email sequence, content piece, ad campaign, outreach contact, subscriber, and experiment across a project — and uses AI to monitor for anomalies, missed deadlines, stale automations, and compounding failures before they become problems.

It is project-based and reusable. Grindlab is project #1. Future products get their own fully independent project with the same infrastructure.

**Access:** http://localhost:5000 in any browser on Phil's Mac Mini.

---

## 2. TECHNOLOGY STACK

| Component | Technology | Notes |
|-----------|-----------|-------|
| Backend | Python 3.14, FastAPI | Already on Mac Mini |
| Frontend | Jinja2 templates + HTMX + Tailwind CSS (CDN) | Server-rendered, no build tools, HTMX for interactions |
| Database | SQLite via SQLAlchemy ORM | File: `data/mcc.db` |
| Scheduler | APScheduler | In-process cron for metric refresh and AI jobs |
| AI Engine | Anthropic API (Claude Sonnet) | Anomaly detection, chat, digest, signals |
| Charts | Chart.js (CDN) | Dark-theme compatible |
| Drag/Drop | Sortable.js (CDN) | Kanban task management |
| HTTP Client | httpx (async) | API integrations with timeout/retry |
| Fonts | Inter (Google Fonts CDN) | Clean, professional |

**Non-negotiable:** No React, no Vue, no SPA. No Docker. No Postgres/Redis. Single Python process. SQLite only.

---

## 3. DIRECTORY STRUCTURE

```
marketing-command-center/
├── app/
│   ├── main.py                    # FastAPI entry, middleware, startup
│   ├── models.py                  # ALL SQLAlchemy models (26 models)
│   ├── database.py                # SQLite engine + session
│   ├── config.py                  # Env vars, API keys, defaults
│   ├── scheduler.py               # APScheduler job definitions
│   ├── routes/
│   │   ├── dashboard.py           # Main dashboard + execution score
│   │   ├── daily.py               # Morning ops view
│   │   ├── calendar_view.py       # Unified marketing calendar
│   │   ├── roadmap.py             # Timeline with critical path
│   │   ├── weekly.py              # Weekly review
│   │   ├── tasks.py               # Task tracker + kanban
│   │   ├── content.py             # Content pipeline tracker
│   │   ├── outreach.py            # Outreach pipeline
│   │   ├── ads.py                 # Paid ad management + signals
│   │   ├── whats_working.py       # Messaging analysis + experiments
│   │   ├── subscribers.py         # Funnel + velocity + attribution + lead scoring
│   │   ├── onboarding.py          # Onboarding journey tracker
│   │   ├── engagement.py          # Retention segments + churn prediction
│   │   ├── feedback.py            # Customer feedback + testimonials
│   │   ├── competitors.py         # Competitive intelligence
│   │   ├── channels.py            # Channel CRUD + detail
│   │   ├── automations.py         # Registry + health + automation advisor
│   │   ├── sequences.py           # Email sequence tracker + win-back
│   │   ├── techstack.py           # Tech stack manager
│   │   ├── budget.py              # Budget planner
│   │   ├── strategy.py            # Strategy document + AI session
│   │   ├── knowledge.py           # Cross-project knowledge base
│   │   ├── projects.py            # Project CRUD + wizard
│   │   ├── partner.py             # Partner dashboard (share links)
│   │   ├── metrics.py             # Metric recording + history
│   │   ├── settings.py            # API keys, thresholds, config
│   │   └── ai.py                  # AI chat + insights endpoint
│   ├── integrations/
│   │   ├── base.py                # Integration abstract base class
│   │   ├── convertkit.py          # Kit: subs, sequences, tags
│   │   ├── instantly.py           # Instantly: sends, opens, replies
│   │   ├── ga4.py                 # GA4: pageviews, conversions, sources
│   │   ├── buffer_api.py          # Buffer: queue, posts, engagement
│   │   ├── meta_ads.py            # Meta Ads: spend, CPL, ROAS
│   │   ├── reddit_ads.py          # Reddit Ads: spend, impressions, CPL
│   │   ├── google_ads.py          # Google/YouTube Ads: spend, views, CTR
│   │   ├── sparkloop.py           # SparkLoop: referrals by tier
│   │   ├── stripe_api.py          # Stripe: MRR, trials, conversions, churn
│   │   ├── railway.py             # Railway/n8n: workflow health
│   │   └── manual.py              # Manual entry handler
│   ├── ai/
│   │   ├── engine.py              # Anthropic API wrapper + prompt mgmt
│   │   ├── anomaly.py             # Metric anomaly detection
│   │   ├── deadline_enforcer.py   # Deadline + dependency chain monitoring
│   │   ├── advisor.py             # Suggested actions + optimization
│   │   ├── ad_signals.py          # Paid ad performance signals
│   │   ├── gap_analyzer.py        # Structural + strategic gap analysis
│   │   └── automation_advisor.py  # Automation opportunity recommendations
│   ├── templates/
│   │   ├── base.html              # Layout, sidebar nav, dark theme
│   │   ├── dashboard.html
│   │   ├── daily.html
│   │   ├── calendar.html
│   │   ├── roadmap.html
│   │   ├── weekly.html
│   │   ├── tasks.html
│   │   ├── content.html
│   │   ├── outreach.html
│   │   ├── ads.html
│   │   ├── whats_working.html
│   │   ├── subscribers.html
│   │   ├── onboarding.html
│   │   ├── engagement.html
│   │   ├── feedback.html
│   │   ├── competitors.html
│   │   ├── channels.html
│   │   ├── channel_detail.html
│   │   ├── automations.html
│   │   ├── sequences.html
│   │   ├── techstack.html
│   │   ├── budget.html
│   │   ├── strategy.html
│   │   ├── knowledge.html
│   │   ├── projects.html
│   │   ├── wizard.html
│   │   ├── partner.html
│   │   ├── settings.html
│   │   ├── chat_panel.html        # AI chat slide-out
│   │   └── partials/              # HTMX partial templates
│   └── static/
│       ├── css/custom.css          # Tailwind overrides, dark theme
│       └── js/app.js               # Chart.js init, HTMX config, shortcuts
├── data/
│   ├── mcc.db                      # SQLite database
│   └── backups/                    # Daily backup target
├── seeds/
│   └── grindlab.py                 # Complete Grindlab pre-load
├── requirements.txt
└── run.py                          # Start command
```

---

## 4. DATA MODEL (26 MODELS)

All models use SQLAlchemy ORM. All are project-scoped (FK to Project) except KnowledgeEntry (which can be global) and ChatConversation/ChatMessage.

### 4.1 Project
```python
class Project(Base):
    id: int  # PK
    name: str  # max 100, e.g. "Grindlab"
    slug: str  # max 50, URL-safe
    status: Enum  # active, paused, archived
    launch_date: date | None  # for countdown
    monthly_budget: Decimal
    notes: str
    created_at: datetime
    updated_at: datetime
```

### 4.2 Channel
```python
class Channel(Base):
    id: int
    project_id: int  # FK -> Project
    name: str  # e.g. "Cold Email (Instantly)"
    channel_type: Enum  # email, social, paid_ads, referral, content, community, cold_outreach, seo, partnerships
    status: Enum  # live, planned, building, blocked, paused, deprecated
    automation_level: Enum  # full_auto, low_touch, manual
    owner: str  # phil, clint, karen, chelsea, scotty, claude, external
    integration_key: str | None  # which integration module pulls data
    health: Enum  # healthy, warning, critical, stale, unknown
    health_reason: str | None
    daily_actions: JSON  # array of strings: what Phil does daily
    auto_actions: JSON  # array of strings: what runs automatically + last_run
    dependencies: JSON  # array of channel_ids
    attributed_mrr: Decimal | None  # calculated: MRR from subs acquired via this channel
    total_spend_to_date: Decimal | None  # calculated: all costs for this channel
    notes: str
    created_at: datetime
    updated_at: datetime
```

### 4.3 Tool (Tech Stack)
```python
class Tool(Base):
    id: int
    project_id: int  # FK -> Project
    name: str  # e.g. "ConvertKit"
    category: Enum  # email_marketing, cold_outreach, analytics, social_mgmt, ads_platform, content_production, automation, referral, payments, hosting, ai_llm, dev_tools, scraping
    purpose: str  # one sentence
    monthly_cost: Decimal
    billing_cycle: Enum  # monthly, annual, one_time, free, usage_based
    status: Enum  # active, planned, evaluating, deprecated, blocked
    blocker: str | None
    api_integrated: bool
    api_key_env_var: str | None
    alternative_to: int | None  # FK -> Tool
    gap_flag: bool  # category missing a tool?
    redundancy_flag: bool  # another tool covers same function?
    last_reviewed: date
    notes: str
```

### 4.4 Task
```python
class Task(Base):
    id: int
    project_id: int  # FK -> Project
    channel_id: int | None  # FK -> Channel
    title: str  # max 200
    description: str  # full detail, acceptance criteria
    status: Enum  # backlog, this_week, in_progress, blocked, done, monitoring, recurring
    priority: Enum  # launch_critical, high, medium, low, cleanup
    assigned_to: str  # phil, clint, karen, chelsea, scotty, claude
    due_date: date | None
    start_date: date | None  # for roadmap view
    estimated_hours: float | None  # for AI timeline optimization
    completed_at: datetime | None
    blocked_by: JSON  # array of task_ids
    blocks: JSON  # array of task_ids
    recurring_schedule: str | None  # cron expression
    recurring_next_due: date | None
    monitoring_metric: str | None
    monitoring_threshold: str | None  # e.g. "open_rate < 15%"
    escalation_hours: int | None  # hours past due before AI escalates
    created_at: datetime
    updated_at: datetime
```

### 4.5 Automation
```python
class Automation(Base):
    id: int
    project_id: int  # FK -> Project
    channel_id: int | None  # FK -> Channel
    name: str  # e.g. "Reddit Daily Brief"
    automation_type: Enum  # cron_job, email_sequence, webhook_pipeline, scheduled_post, referral_program, ad_campaign
    platform: str  # e.g. "Mac Mini cron", "ConvertKit", "Railway n8n"
    schedule: str | None  # cron or description
    expected_run_interval_hours: int | None
    last_confirmed_run: datetime | None
    health: Enum  # running, stale, failed, paused, unknown
    health_check_method: Enum  # api_poll, log_check, manual_confirm, webhook_heartbeat
    health_check_config: JSON
    owner: str
    script_path: str | None
    notes: str
```

### 4.6 EmailSequence
```python
class EmailSequence(Base):
    id: int
    project_id: int  # FK -> Project
    name: str  # e.g. "Nurture Drip v3"
    sequence_type: Enum  # nurture_drip, broadcast, transactional, triggered, onboarding, retention, win_back
    platform: str  # e.g. "ConvertKit", "Resend"
    email_count: int
    status: Enum  # live, draft, needs_copy, needs_build, planned, paused
    trigger: str  # what starts this sequence
    open_rate: Decimal | None
    click_rate: Decimal | None
    subscribers_active: int | None
    last_reviewed: date | None
    notes: str
```

### 4.7 AdCampaign
```python
class AdCampaign(Base):
    id: int
    project_id: int  # FK -> Project
    channel_id: int  # FK -> Channel
    platform: Enum  # meta, reddit, google, youtube, x_twitter, tiktok
    campaign_name: str
    campaign_id_external: str | None  # platform's ID for API
    status: Enum  # active, paused, ended, scheduled, draft
    objective: Enum  # traffic, conversions, awareness, retargeting, engagement
    daily_budget: Decimal
    total_budget: Decimal | None
    spend_to_date: Decimal
    impressions: int
    clicks: int
    ctr: Decimal
    conversions: int
    cpl: Decimal | None  # cost per lead
    roas: Decimal | None  # return on ad spend
    cpm: Decimal | None
    signal: Enum  # scale, hold, optimize, pause, kill
    signal_reason: str | None
    creative_notes: str | None
    start_date: date
    end_date: date | None
    last_synced: datetime | None
    notes: str
```

**Ad Signal Rules:**
- SCALE: CPL < target AND conversion rate > threshold AND spend < 50% budget
- HOLD: CPL within 20% of target AND conversion rate acceptable
- OPTIMIZE: CTR declining OR CPL rising but within 40% of target
- PAUSE: CPL > 2x target OR CTR < 0.5% OR conversion rate < 1%
- KILL: Spent > 50% budget with zero conversions OR CPL > 3x target
- Minimum data before signal: 100 impressions and $10 spend

**Grindlab defaults:** Target CPL $5.00, target CTR 1.5%, target conversion 3%.

### 4.8 ContentPiece
```python
class ContentPiece(Base):
    id: int
    project_id: int  # FK -> Project
    title: str
    series: str  # e.g. "Study Science Drop", "Room Report"
    content_type: Enum  # short_video, long_video, text_post, thread, blog, email, graphic
    production_lane: Enum  # lane1_text_motion, lane2_raw_capture, lane3_selfie, lane4_produced
    status: Enum  # concept, scripted, filmed, with_editor, edited, scheduled, published
    assigned_to: str
    platform_target: JSON  # array: ["youtube_shorts", "ig_reels", "tiktok", "x", "reddit"]
    script_source: str | None
    due_date: date | None
    published_at: datetime | None
    published_urls: JSON  # {youtube: url, ig: url, ...}
    performance: JSON | None  # {views: X, likes: X, comments: X} per platform
    notes: str
```

### 4.9 Metric + MetricSnapshot
```python
class Metric(Base):
    id: int
    channel_id: int  # FK -> Channel
    metric_name: str  # e.g. "subscribers", "open_rate"
    metric_value: Decimal
    previous_value: Decimal | None
    unit: str  # count, percent, dollars, rate
    source: Enum  # api, manual
    recorded_at: datetime

class MetricSnapshot(Base):
    id: int
    channel_id: int  # FK -> Channel
    metric_name: str
    value: Decimal
    snapshot_date: date  # one per day per metric
```

### 4.10 AIInsight
```python
class AIInsight(Base):
    id: int
    project_id: int  # FK -> Project
    insight_type: Enum  # anomaly, deadline_warning, dependency_risk, stale_automation, ad_signal, suggestion, trend, gap_analysis, weekly_digest, bottleneck, experiment_result
    source_type: Enum  # channel, task, automation, ad_campaign, tool, sequence, content, subscriber, onboarding, general
    source_id: int | None
    title: str
    body: str
    severity: Enum  # info, attention, urgent, critical
    action_items: JSON  # array of suggested actions, each convertible to task
    acknowledged: bool
    created_at: datetime
```

### 4.11 OutreachContact
```python
class OutreachContact(Base):
    id: int
    project_id: int  # FK -> Project
    name: str
    platform: str  # YouTube, Instagram, Twitter, LinkedIn, Discord, In-Person
    audience_size: int | None
    contact_type: Enum  # influencer, coach, ambassador_prospect, affiliate_prospect, partnership
    status: Enum  # identified, contacted, responded, in_conversation, committed, active, declined, ghosted
    last_contact_date: date | None
    next_follow_up: date | None  # AI flags overdue
    outreach_stage: int  # 1=intro, 2=product access, 3=feedback, 4=partnership ask
    commission_tier: str | None
    referral_link: str | None
    notes: str
```

### 4.12 ChatConversation + ChatMessage
```python
class ChatConversation(Base):
    id: int
    project_id: int  # FK -> Project
    title: str  # AI-generated 3-5 word title
    pinned: bool
    created_at: datetime
    updated_at: datetime

class ChatMessage(Base):
    id: int
    conversation_id: int  # FK -> ChatConversation
    role: Enum  # user, assistant, system
    content: str
    tool_calls: JSON | None
    tool_results: JSON | None
    context_snapshot: JSON | None  # what data was included
    created_at: datetime
```

### 4.13 PartnerView
```python
class PartnerView(Base):
    id: int
    project_id: int  # FK -> Project
    name: str  # e.g. "Clint View"
    token: str  # UUID for URL
    preset: str  # technical_cofounder, editor, investor, affiliate, full_readonly, custom
    custom_config: JSON  # which components to show
    banner_text: str | None
    is_active: bool
    last_accessed: datetime | None
    created_at: datetime
```

### 4.14 SubscriberSnapshot + SubscriberEvent
```python
class SubscriberSnapshot(Base):
    id: int
    project_id: int  # FK -> Project
    snapshot_date: date
    stage: Enum  # waitlist_lead, free_trial_active, free_trial_expired, paid_basic, paid_premium, churned, paused
    count: int
    mrr: Decimal | None  # for paid stages
    created_at: datetime

class SubscriberEvent(Base):
    id: int
    project_id: int  # FK -> Project
    email_hash: str  # NOT actual email
    event_type: Enum  # trial_start, trial_expire, convert_basic, convert_premium, churn, pause, reactivate
    source_channel_id: int | None  # FK -> Channel (for attribution)
    occurred_at: datetime
```

### 4.15 ContentTag + PerformanceScore
```python
class ContentTag(Base):
    id: int
    content_piece_id: int | None
    email_sequence_id: int | None
    ad_campaign_id: int | None
    outreach_id: int | None
    tag_dimension: Enum  # hook_type, topic, pillar, tone, format, cta_type, audience
    tag_value: str
    created_at: datetime

class PerformanceScore(Base):
    id: int
    content_piece_id: int | None
    email_sequence_id: int | None
    ad_campaign_id: int | None
    platform: str
    views: int
    clicks: int
    conversions: int
    engagement_score: Decimal  # calculated composite
    recorded_at: datetime
```

### 4.16 ProjectStrategy
```python
class ProjectStrategy(Base):
    id: int
    project_id: int  # FK -> Project
    section: Enum  # product, customer, competitors, messaging, voice, pillars, budget
    content: str  # markdown/rich text
    ai_conversation_id: int | None  # FK -> ChatConversation
    created_at: datetime
    updated_at: datetime
```

### 4.17 BudgetAllocation + BudgetExpense
```python
class BudgetAllocation(Base):
    id: int
    project_id: int  # FK -> Project
    category: Enum  # tools_services, paid_advertising, content_production, lead_acquisition, events_travel, reserve
    planned_monthly: Decimal
    period_start: date
    notes: str

class BudgetExpense(Base):
    id: int
    project_id: int  # FK -> Project
    category: Enum  # same as BudgetAllocation
    amount: Decimal
    description: str
    tool_id: int | None  # FK -> Tool
    ad_campaign_id: int | None  # FK -> AdCampaign
    expense_date: date
    source: Enum  # auto, manual
```

### 4.18 Competitor + CompetitorUpdate
```python
class Competitor(Base):
    id: int
    project_id: int  # FK -> Project
    name: str
    website: str
    pricing_summary: str
    positioning_summary: str
    strengths: str
    weaknesses: str
    key_channels: JSON  # array
    last_checked: date
    notes: str

class CompetitorUpdate(Base):
    id: int
    competitor_id: int  # FK -> Competitor
    update_type: Enum  # pricing_change, feature_launch, content_observed, partnership, funding, other
    summary: str
    source_url: str | None
    observed_at: datetime
    created_by: str  # phil or ai
```

### 4.19 KnowledgeEntry
```python
class KnowledgeEntry(Base):
    id: int
    project_id: int | None  # NULL = global (cross-project)
    entry_type: Enum  # lesson, tool_decision, playbook, benchmark, pattern
    title: str
    body: str  # markdown
    tags: JSON  # array
    source_project: str
    source_conversation_id: int | None
    auto_generated: bool
    confirmed: bool  # Phil must confirm AI-generated
    created_at: datetime
    updated_at: datetime
```

### 4.20 Experiment
```python
class Experiment(Base):
    id: int
    project_id: int  # FK -> Project
    channel_id: int | None  # FK -> Channel
    hypothesis: str
    test_type: Enum  # email_subject, landing_page, ad_creative, content_hook, cta_placement, pricing
    variant_a: str  # control
    variant_b: str  # challenger
    success_metric: str
    sample_target: int | None
    duration_days: int | None
    status: Enum  # draft, running, complete, inconclusive
    winner: Enum | None  # a, b, inconclusive
    result_summary: str | None
    decision: str | None
    knowledge_entry_id: int | None  # FK -> KnowledgeEntry
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
```

### 4.21 LeadScore
```python
class LeadScore(Base):
    id: int
    project_id: int  # FK -> Project
    email_hash: str  # NOT actual email
    current_score: int
    tier: Enum  # hot (50+), warm (20-49), cool (5-19), cold (<5)
    source_channel_id: int | None
    last_activity_at: datetime
    scoring_events: JSON  # array of {action, points, timestamp}
    created_at: datetime
    updated_at: datetime
```

**Lead Scoring Actions:**
- Signed up for email list: +5
- Opened a nurture email: +2 each (max 5)
- Clicked link in email: +5 each
- Completed Leak Finder quiz: +15
- Visited pricing page: +10 (first time), +20 (repeat)
- Replied to email: +25
- Referred someone: +15
- Downloaded PDF: +10
- Visited site 3+ times/week: +10
- Inactive 14+ days: -10 decay
- Inactive 30+ days: -20 additional decay

### 4.22 CustomerFeedback
```python
class CustomerFeedback(Base):
    id: int
    project_id: int  # FK -> Project
    source: Enum  # email, survey, social, support, exit_survey, manual
    feedback_type: Enum  # testimonial, feature_request, complaint, nps, cancellation_reason, use_case
    content: str
    sentiment: Enum  # positive, neutral, negative
    themes: JSON  # array, AI-tagged
    can_use_publicly: bool
    customer_identifier: str | None  # hashed
    nps_score: int | None
    ai_summary: str | None
    created_at: datetime
```

### 4.23 OnboardingMilestone + OnboardingProgress
```python
class OnboardingMilestone(Base):
    id: int
    project_id: int  # FK -> Project
    name: str  # e.g. "Complete Leak Finder quiz"
    description: str
    target_days_from_start: int
    display_order: int
    intervention_sequence_id: int | None  # FK -> EmailSequence
    created_at: datetime

class OnboardingProgress(Base):
    id: int
    project_id: int  # FK -> Project
    subscriber_hash: str
    milestone_id: int  # FK -> OnboardingMilestone
    completed: bool
    completed_at: datetime | None
    intervention_sent: bool
    intervention_sent_at: datetime | None
    created_at: datetime
```

---

## 5. SIDEBAR NAVIGATION

Organized by how Phil's day flows: check status → execute → analyze → manage systems.

### Operations (Check Status)
- **Dashboard** (home) — Execution score, channel grid, urgent items
- **Daily Ops** (sun) — Morning briefing
- **Calendar** (calendar-days) — Unified marketing calendar
- **Roadmap** (gantt-chart) — Timeline with critical path
- **Weekly Review** (bar-chart) — Full metrics review

### Execution (Do Work)
- **Tasks** (check-square) — Kanban board (7 columns)
- **Content** (film) — Content pipeline kanban
- **Outreach** (users) — Influencer/ambassador/affiliate pipeline
- **Ads** (megaphone) — Campaigns + signals

### Intelligence (Analyze)
- **What's Working** (trending-up) — Messaging leaderboard + experiments
- **Subscribers** (user-plus) — Funnel + velocity + attribution + lead scoring
- **Onboarding** (rocket) — Journey tracker + milestones
- **Engagement** (activity) — Retention segments + churn prediction
- **Feedback** (message-circle) — Customer feedback + testimonials
- **Competitors** (eye) — Competitive intelligence

### System (Manage)
- **Channels** (grid) — All channels + detail views
- **Automations** (cpu) — Registry + health + advisor
- **Sequences** (mail) — Email sequences + win-back
- **Tech Stack** (wrench) — Tools + gaps + review
- **Budget** (wallet) — Planner + actual vs planned
- **Strategy** (compass) — Strategy doc + AI session

### Global
- **Knowledge Base** (book-open) — Cross-project memory
- **Projects** (folder) — Switcher + wizard
- **Settings** (settings) — API keys, thresholds, partner views

### Persistent (Always Accessible)
- **AI Chat** (Ctrl+Space) — Slide-out panel from right
- **Quick Actions** — + Task, + Metric, + Content (top bar, every page)

---

## 6. UI DESIGN

**Theme:** Dark. Background #0F0F23, cards #1A1A2E, card borders #2A2A3E, primary accent #E94560, secondary #0F3460, text #F0F0F0, secondary text #8B8B9E, success #00C853, warning #FFB300, critical #FF1744.

**Typography:** Inter font (Google Fonts CDN). Headings 600 weight (24/20/16px). Body 400 weight 14px. Metric values 700 weight 28px. Mono: JetBrains Mono 13px.

**Components:**
- Cards with 8px rounded corners, subtle border, hover shadow
- Health dots: 8px filled circles, pulse animation on critical
- Metric display: large number + delta badge (green ▲ / red ▼) + label
- Solid accent buttons for primary, outlined for secondary
- Chart.js with dark background, 10% opacity gridlines
- Kanban columns with drag handles (Sortable.js)
- HTMX for all interactions — no full page reloads
- Loading spinners in-place during HTMX swaps

**Responsive:** Desktop primary (1280px+). Sidebar collapses to icons at 1024px. No mobile optimization in v1.

---

## 7. EXECUTION GUARANTEE SYSTEM

The core intelligence that prevents compounding failures.

### 7.1 Execution Score (0-100)

| Component | Weight | Scoring |
|-----------|--------|---------|
| Tasks on track | 25% | 100 = zero overdue; -5 per overdue; -10 per launch-critical overdue |
| Automations healthy | 20% | 100 = all running; -15 per stale; -25 per failed |
| Channels healthy | 20% | 100 = all healthy; -10 per warning; -20 per critical |
| Content pipeline | 15% | 100 = at/above weekly target; proportional reduction below |
| Recurring tasks done | 10% | 100 = all done on time; proportional reduction |
| Outreach follow-ups | 10% | 100 = none overdue; -5 per overdue |

Thresholds: 85+ green, 70-84 yellow, below 70 red.

### 7.2 Deadline Enforcer (Every 6 hours)
- 48hr before due: info reminder
- 24hr before due: attention alert
- Overdue: urgent alert + downstream impact analysis
- Overdue + has `blocks` dependencies: critical alert + full chain shown

### 7.3 Automation Staleness (Every 4 hours)
- last_confirmed_run > 1.5x expected interval: stale warning
- last_confirmed_run > 3x expected interval: failed urgent alert

### 7.4 Channel Health Rules
- Email Nurture: warning if open rate < 20% or no new subs in 48hr
- Cold Email: warning if reply rate = 0% after 500+ sends; critical if bounce > 5%
- Social: warning if Buffer queue < 3 days; stale if no posts in 48hr
- Reddit: stale if no engagement in 48hr
- YouTube/Content: warning if no new content in 7 days
- Paid Ads: signal-based (Section 4.7)
- Referral/Affiliate: stale if no new referral in 14 days post-launch
- Leak Finder: warning if completions drop 30% vs 7-day avg

### 7.5 Recurring Task Engine
Auto-generates new task instance each cycle. Tracks streaks (consecutive completed / missed). If previous instance not done, new one flags it.

### 7.6 Gap Analysis (Weekly)
**Structural:** Channels with no tasks, tools in planned past setup date, sequences needing copy approaching trigger date, empty pipeline stages, overdue follow-ups, tool gaps, budget overruns.
**Strategic:** Missing growth levers vs common SaaS playbooks, competitive positioning drift, channel concentration risk, content pillar coverage gaps, SEO opportunity, automation maturity.

---

## 8. AI LAYER

### 8.1 Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Deadline Enforcer | Every 6 hours | Tasks: upcoming/overdue + dependency chains |
| Anomaly Detector | Daily 6AM | Metrics: 7-day avg comparison, >15% flag |
| Automation Health | Every 4 hours | All automations: staleness check |
| Ad Signal Calculator | Every 6 hours | Recalculate all active campaign signals |
| Gap Analyzer | Weekly Sunday | Structural + strategic gap analysis |
| Weekly Digest | Sunday 7AM | Full project summary |
| Outreach Follow-Up | Daily 8AM | Flag overdue contact follow-ups |
| Content Pipeline Check | Daily 9AM | Content output vs weekly target |

### 8.2 AI Chat Interface
- Persistent slide-out panel (right side, 35-40% width, Ctrl+Space toggle)
- Full conversation history in SQLite
- Tool calling (Claude tool use) for data access and actions
- Page-context aware: knows what view Phil is looking at
- Quick action buttons: "Morning briefing", "What needs attention?", "Weekly summary"

**Chat Tools:**
- get_channel_metrics(channel_id, days)
- get_task_list(filters)
- create_task(title, priority, due_date, channel, assignee)
- update_task(task_id, status)
- record_metric(channel_id, metric_name, value)
- get_ad_campaigns(filters)
- get_execution_score()
- get_outreach_contacts(filters)
- get_automations(health_filter)
- get_content_pipeline(status_filter)
- get_subscriber_funnel()
- search_whats_working(channel, metric, days)
- get_tech_stack(category)
- get_weekly_summary()

### 8.3 Estimated AI Cost: ~$12/month (Claude Sonnet)

---

## 9. API INTEGRATIONS

Each inherits from IntegrationBase with connect(), fetch_metrics(), get_health_status(). Missing API keys = graceful fallback to manual entry. 3 consecutive failures = channel health warning + AIInsight.

| Integration | Metrics | Refresh | Env Var |
|------------|---------|---------|---------|
| convertkit | Subs, new today, by tag, sequence open/click | 4hr | CONVERTKIT_API_SECRET |
| instantly | Sent, opens, replies, bounces | 6hr | INSTANTLY_API_KEY |
| ga4 | Pageviews, sessions, conversions, sources | 6hr | GA4_CREDENTIALS_PATH + GA4_PROPERTY_ID |
| buffer | Queue count, sent, engagement, gap days | 4hr | BUFFER_ACCESS_TOKEN |
| meta_ads | Spend, impressions, clicks, CTR, CPL, ROAS | 6hr | META_ADS_ACCESS_TOKEN |
| reddit_ads | Spend, impressions, clicks, CTR, CPL | 6hr | REDDIT_ADS_TOKEN |
| google_ads | Spend, impressions, clicks, CTR, video views | 6hr | GOOGLE_ADS_CREDENTIALS |
| stripe | MRR, trials, conversion rate, churn | 4hr | STRIPE_API_KEY |
| sparkloop | Referrals by tier | Daily | SPARKLOOP_API_KEY |
| railway | Workflow execution status | 4hr | RAILWAY_API_KEY |

**Scotty API endpoints (built into v1):**
- POST /api/metrics/record — Scotty scripts push metrics directly
- POST /api/automations/heartbeat — Scotty reports execution health

---

## 10. GRINDLAB SEED DATA

The `seeds/grindlab.py` file pre-loads ALL of the following on first run:

### 10.1 Channels (14)
Email Nurture (Kit) [live, full_auto, convertkit], Cold Email (Instantly) [live, full_auto, instantly], Leak Finder Quiz [live, full_auto, ga4], Reddit Engagement [live, low_touch, manual], X/Twitter [live, low_touch, buffer], Instagram [live, low_touch, buffer], YouTube [live, manual, manual], SparkLoop Referral [live, full_auto, manual], Influencer Outreach [planned, manual, manual], TikTok [planned, manual, manual], Rumble [planned, manual, manual], Paid Ads [planned, manual, manual], Ambassador Program [planned, manual, manual], Affiliate Program [planned, manual, manual]

Each with appropriate daily_actions and auto_actions arrays.

### 10.2 Tools (17+)
Every tool from the tech stack: ConvertKit ($79), Instantly ($97), Railway ($5), Resend (free), Buffer (free), X Premium ($4), SparkLoop (free), OpenRouter ($0.09), GA4 (free), GTM (free), Meta Pixel (free), Hotjar (free), Karen ($600-1000), Vercel (free), Supabase (free), Rewardful ($49, planned), Phantombuster ($69, planned).

### 10.3 Tasks (40+)
All from Master Brief "What Still Needs Doing" with correct priority, assignee, due date, and dependency chains:
- Launch countdown email sequence (launch_critical, Mar 23)
- Trial expiration flow (launch_critical, Mar 28)
- Onboarding activation email (launch_critical, Mar 28)
- Cancellation/pause flow spec (launch_critical, Mar 25)
- Purchase page copy (launch_critical, Mar 20)
- Website strategy decision (launch_critical, Mar 10)
- Cold email angle audit (launch_critical, Mar 12)
- Create TikTok account (launch_critical, Mar 10)
- Create Rumble account (launch_critical, Mar 10)
- Activate subscribers for testimonials (launch_critical, Mar 12)
- Plus 30+ more across all priority levels

### 10.4 Automations (10+)
Reddit Daily Brief (7AM daily), Milestone Alerts (4hr), Weekly Metrics Rollup (Sun 8AM), Pipeline Health Check (on-demand), Kit Nurture v3 (triggered), n8n Leak Finder Pipeline (triggered), n8n Instantly-Reply Pipeline (triggered), Buffer Scheduled Posts (scheduled), Instantly Warmup/Send (continuous), SparkLoop Referral Tracking (continuous)

### 10.5 Email Sequences (6)
Nurture v3 [live, 7 emails], Leak Finder Results [live, 1 email], Lead Magnet Delivery [live, 1 email], Launch Countdown [not built, 6-8 emails], Trial Expiration [not built, 3 emails], Onboarding Activation [not built, 1 email]

### 10.6 Competitors (4)
Upswing Poker ($99-199 courses), PokerCoaching.com ($30/mo), GTO Wizard (varies), Run It Once (varies). Each with positioning, strengths, weaknesses, gap.

### 10.7 Outreach Contacts
Top 10 priority influencers: Lexy Gavin-Mather (289K), hungry horse poker (184K), plus 8 more. All set to "identified" status.

### 10.8 Onboarding Milestones (8)
Complete Leak Finder (Day 1), Log first session (Day 1-2), Record first hand (Day 2-3), Complete first study plan (Day 3-5), Return for second session (Day 5-7), Run a drill (Day 7-14), Active in Week 3 (Day 14-21), Trial Day 25+ (conversion window).

### 10.9 Initial Metrics
112 Kit subscribers, 250 Instantly sends, 0 replies, and any other known current metrics.

---

## 11. ENVIRONMENT VARIABLES

| Variable | Required For |
|----------|-------------|
| ANTHROPIC_API_KEY | AI features (chat, insights, scheduled jobs) |
| CONVERTKIT_API_SECRET | Kit integration |
| INSTANTLY_API_KEY | Instantly integration |
| GA4_CREDENTIALS_PATH | GA4 integration (service account JSON path) |
| GA4_PROPERTY_ID | GA4 integration |
| BUFFER_ACCESS_TOKEN | Buffer integration |
| STRIPE_API_KEY | Stripe integration (post-launch) |
| META_ADS_ACCESS_TOKEN | Meta Ads integration |
| REDDIT_ADS_TOKEN | Reddit Ads integration |
| GOOGLE_ADS_CREDENTIALS | Google/YouTube Ads integration |
| SPARKLOOP_API_KEY | SparkLoop integration (if available) |
| RAILWAY_API_KEY | Railway integration |
| LAUNCH_COMMAND_PORT | No (default 5000) |
| LAUNCH_COMMAND_DB_PATH | No (default data/mcc.db) |

**All integrations fail gracefully.** Missing key = manual entry fallback, not crash. Missing ANTHROPIC_API_KEY = no AI features, app fully functional otherwise.

---

## 12. IMPLEMENTATION PHASES

Build in order. Each phase produces a testable increment. Do not skip phases.

### Phase 1: Foundation (Day 1-2)
1. Project structure per Section 3
2. requirements.txt: fastapi, uvicorn[standard], sqlalchemy, jinja2, httpx, apscheduler, anthropic, python-multipart
3. database.py with SQLite
4. models.py with ALL 26 models
5. seeds/grindlab.py with ALL seed data from Section 10
6. run.py: init DB, run seeds if empty, start FastAPI on port 5000
7. base.html: dark theme, full sidebar nav, quick actions bar, keyboard shortcuts, HTMX + Tailwind CDN
8. **Verify:** app starts, DB creates, seeds load, base page renders

### Phase 2: Dashboard + Channels + Funnel (Day 3-4)
1. Dashboard: execution score, channel health grid, urgent items, AI insights panel
2. Channel detail view with metric charts
3. HTMX partial swap for channel expansion
4. Manual metric entry form
5. Subscriber funnel view (manual data pre-launch)
6. **Verify:** all 14 channels visible, click-through works, metrics display, funnel renders

### Phase 3: Tasks + Roadmap (Day 5-6)
1. Kanban board (7 columns: backlog, this_week, in_progress, blocked, done, monitoring, recurring)
2. Drag-and-drop via Sortable.js + HTMX persistence
3. Task create/edit modal with dependency fields
4. Dependency chain visualization on hover
5. Recurring task auto-generation
6. Timeline/Roadmap view with critical path, dependency arrows, today marker
7. **Verify:** all 40+ tasks visible, drag works, dependencies show, roadmap renders

### Phase 4: Daily + Calendar + Weekly (Day 7-8)
1. Daily ops: today's tasks, automation status, overnight changes
2. Marketing calendar: aggregates content, emails, ads, events on time grid
3. Weekly review: metrics table, milestones, spend, task velocity
4. Recurring task streak tracking
5. **Verify:** morning view actionable, calendar shows cross-channel items, weekly comprehensive

### Phase 5: Pipelines (Day 9-10)
1. Automation registry with health indicators + staleness detection
2. Email sequence view with status and pipeline visualization
3. Content pipeline kanban (concept → published)
4. Outreach pipeline with follow-up tracking
5. Onboarding journey tracker with milestone funnel
6. Customer feedback view with testimonial bank
7. **Verify:** all pipelines render, CRUD works, follow-up flags show

### Phase 6: Ads + Tech Stack + Budget + What's Working (Day 11-12)
1. Ad campaign management with signal system
2. Tech stack manager with gap/redundancy detection
3. Budget planner: allocation, actual vs planned, burn rate
4. Content tagging + messaging leaderboard
5. Experiment tracker (A/B testing)
6. Channel ROI attribution (partial — full when Stripe live)
7. **Verify:** signals calculate, gaps flagged, budget tracks, leaderboard ranks

### Phase 7: API Integrations (Day 13-15)
1. IntegrationBase abstract class
2. ConvertKit, Instantly, GA4, Buffer integrations
3. Stripe integration (ready for post-launch)
4. Ad platform integrations (Meta, Reddit, Google — framework ready)
5. APScheduler with all refresh intervals
6. Health auto-update on API success/failure
7. POST /api/metrics/record + /api/automations/heartbeat (Scotty endpoints)
8. **Verify:** metrics auto-populate, health reflects reality

### Phase 8: AI Layer + Chat (Day 16-18)
1. ai/engine.py: Anthropic API wrapper with tool use
2. All 8 scheduled AI jobs (Section 8.1)
3. Execution score calculation
4. AI Chat panel: slide-out, conversation history, tool calling, page context
5. Deadline enforcer with dependency chains
6. Automation advisor (recommendations for what to automate next)
7. Strategic gap analysis
8. Insight-to-task conversion (one click)
9. **Verify:** insights generate, chat returns useful answers, score calculates

### Phase 9: Strategy + Wizard + Knowledge + Partners (Day 19-21)
1. Strategy builder: AI-guided conversation → structured document
2. 7-step project wizard with AI assistance
3. Template system (Grindlab becomes a template)
4. Knowledge base (cross-project, manual + AI-suggested)
5. Competitive intelligence view
6. Retention/engagement tracking view
7. Win-back segment calculations
8. Partner dashboard with share links and presets
9. **Verify:** wizard creates populated project, knowledge persists, partner links work

### Phase 10: Polish (Day 22-25)
1. All keyboard shortcuts working
2. Global search across all entity types
3. Cross-links between all entities (channel → tasks, task → channel, insight → source)
4. Empty states for new projects
5. Loading states for all HTMX interactions
6. Final visual polish pass
7. Full end-to-end testing per checklist below
8. **Verify:** everything in the testing checklist passes

---

## 13. TESTING CHECKLIST

1. `python run.py` starts with no errors
2. localhost:5000 shows Grindlab dashboard with all 14 channels
3. Execution score displays and calculates correctly
4. Click channel card → detail loads via HTMX
5. Enter manual metric → appears on card immediately
6. Create task → correct kanban column
7. Drag task between columns → persists after refresh
8. Roadmap shows tasks on timeline with dependency arrows
9. Critical path highlights correctly
10. Recurring tasks auto-populate daily
11. Daily view shows correct actions per channel
12. Calendar shows items from content, emails, ads, events
13. Weekly view shows metrics with deltas and sparklines
14. All 10+ automations show with correct health
15. All 6 email sequences show with status
16. Content pipeline kanban works (concept → published)
17. Outreach pipeline with follow-up flags works
18. Onboarding milestones display with funnel
19. Customer feedback CRUD works
20. Ad campaigns display with signals
21. Tech stack with gap/redundancy flags
22. Budget: actual vs planned calculates
23. What's Working leaderboard ranks content
24. Experiment tracker CRUD works
25. Subscriber funnel shows stage breakdown
26. Lead scoring tiers calculate
27. Competitor tracker displays
28. Knowledge base CRUD + cross-project search
29. Strategy builder saves sections
30. AI chat opens (Ctrl+Space), maintains history, creates tasks via tool calling
31. Partner share link generates, renders read-only view
32. Project wizard walks all 7 steps, creates populated project
33. Switch to blank project → empty state. Switch back → data intact.
34. All API integrations pull data without errors (if keys configured)
35. Global search returns results from all entity types
36. All keyboard shortcuts work
37. Cross-links navigate correctly between all entity types

---

## 14. DEPLOYMENT

```bash
cd ~/marketing-command-center
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Access: http://localhost:5000

Daily backup cron:
```bash
0 2 * * * cp ~/marketing-command-center/data/mcc.db ~/marketing-command-center/data/backups/mcc_$(date +\%Y\%m\%d).db
```

For persistent running: tmux session or launchd plist.
