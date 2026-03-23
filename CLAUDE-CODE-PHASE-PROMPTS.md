# CLAUDE CODE PHASE PROMPTS
# Use these prompts after each phase completes successfully.
# Test the previous phase first, then paste the next prompt.

---

## AFTER PHASE 1 (Foundation) IS CONFIRMED WORKING:

Phase 1 is working. Move to Phase 2: Dashboard + Channels + Funnel.

Build:
- Dashboard page with execution score (calculated per Section 7.1), channel health grid (card per active channel with health dot, automation badge, 2-3 key metrics with deltas), and urgent items section (overdue tasks, critical health, stale automations)
- Channel detail view with metric history charts (Chart.js, dark theme), daily/auto actions, related tasks
- HTMX partial swap: clicking a channel card loads the detail view without page reload
- Manual metric entry form (select channel, metric name, value — saves to Metric table)
- Subscriber funnel view showing counts per stage from SubscriberSnapshot data
- AI insights panel on dashboard (shows latest AIInsight records, with dismiss button)

Refer to MCC-COMPLETE-SPEC.md Section 5 for sidebar structure, Section 6 for UI design, Section 7.1 for execution score calculation.

---

## AFTER PHASE 2 IS CONFIRMED WORKING:

Phase 2 is working. Move to Phase 3: Tasks + Roadmap.

Build:
- Kanban board with 7 columns: backlog, this_week, in_progress, blocked, done, monitoring, recurring
- Drag-and-drop between columns using Sortable.js, persisting status change to DB via HTMX POST
- Task create/edit modal with all fields including blocked_by and blocks (dependency fields)
- When hovering a task, highlight tasks it blocks and tasks that block it (dependency visualization)
- Recurring task engine: tasks with recurring_schedule auto-generate a new instance when recurring_next_due passes. If previous instance wasn't completed, flag it.
- Timeline/Roadmap view: horizontal time axis (today to launch date), tasks as bars from start_date to due_date, dependency arrows between connected tasks, today marker as vertical line, critical path highlighted (longest dependency chain to launch). Overdue tasks shown in red. Filter by channel, assignee, priority.

---

## AFTER PHASE 3 IS CONFIRMED WORKING:

Phase 3 is working. Move to Phase 4: Daily + Calendar + Weekly.

Build:
- Daily Ops view with 3 sections:
  1. "Your Tasks Today" — manual actions due, grouped by channel, checkboxes, overdue from yesterday in red at top
  2. "Autonomous Systems Status" — every Automation record with last_run and health (green/yellow/red)
  3. "What Changed Overnight" — metrics with >10% change since yesterday
- Marketing Calendar: monthly/weekly grid aggregating scheduled content (ContentPiece), email broadcasts (EmailSequence), ad campaign dates (AdCampaign), task due dates (launch-critical only), events (manual). Color-coded by type.
- Weekly Review: metrics table (every channel, every metric, this week vs last week, delta, sparkline), milestone progress bars, spend report (tools + ads vs budget), task velocity (completed vs added this week), content pipeline summary, outreach pipeline summary.
- Recurring task streak tracking: show consecutive days completed / missed on recurring tasks.

---

## AFTER PHASE 4 IS CONFIRMED WORKING:

Phase 4 is working. Move to Phase 5: Pipelines.

Build:
- Automation registry: list all Automation records with health indicator, last run, expected interval, owner. Timeline showing when each ran and when next expected. Failure log history.
- Email sequence view: all EmailSequence records with name, type, platform, email count, status badge, trigger, open/click rates. Visual pipeline showing how sequences connect.
- Content pipeline kanban: columns = concept, scripted, filmed, with_editor, edited, scheduled, published. Filter by series, content type, assignee, platform. Weekly target indicator. Cross-post tracker.
- Outreach pipeline kanban: columns = identified, contacted, responded, in_conversation, committed, active, declined. Filter by contact type. Follow-up flags for overdue next_follow_up dates.
- Onboarding journey: milestone funnel (% completing each milestone), cohort comparison, individual progress tracking, milestone velocity. Use OnboardingMilestone + OnboardingProgress models.
- Customer feedback: CRUD form (source, type, content, sentiment, can_use_publicly). Feed view filterable by type/sentiment/theme. Testimonial bank (can_use_publicly = true items).

---

## AFTER PHASE 5 IS CONFIRMED WORKING:

Phase 5 is working. Move to Phase 6: Ads + Tech Stack + Budget + What's Working.

Build:
- Ad campaign management: all AdCampaign records with signal badge (SCALE/HOLD/OPTIMIZE/PAUSE/KILL), key metrics, sparklines. Signal calculation per rules in Section 4.7. Summary: total daily spend, conversions, blended CPL, burn rate. Click to expand with full history and AI signal explanation.
- Tech stack manager: all Tools grouped by category. Monthly cost total. Gap flags (category missing active tool). Redundancy flags (multiple tools same category). Review reminders (not reviewed in 60+ days). Tool evaluation workflow (add with status "evaluating", link to alternative_to).
- Budget planner: allocation by category (BudgetAllocation), actual vs planned (BudgetExpense summed), burn rate projection, trend chart. Visual: bar or donut for allocation, side-by-side for actual vs planned.
- Content tagging: when creating/editing ContentPiece, add ContentTag records (hook_type, topic, pillar, tone, format, cta_type, audience). Messaging leaderboard: rank content by PerformanceScore. Cross-channel pattern display.
- Experiment tracker: CRUD for Experiment model. List with status, hypothesis preview, result. Detail view with full data.
- Channel ROI: attribution table per channel (leads, trials, conversions, MRR attributed, CAC, LTV:CAC). Data from SubscriberEvent source_channel_id + BudgetExpense.

---

## AFTER PHASE 6 IS CONFIRMED WORKING:

Phase 6 is working. Move to Phase 7: API Integrations.

Build:
- IntegrationBase abstract class: connect() -> bool, fetch_metrics() -> list[MetricReading], get_health_status() -> HealthStatus
- ConvertKit integration: GET /v3/subscribers, GET /v3/sequences/{id}, GET /v3/forms/{id}. Refresh 4hr.
- Instantly integration: GET /api/v1/analytics/campaign/summary, GET /api/v1/campaign/list. Refresh 6hr.
- GA4 integration: Data API runReport for pageviews, sessions, conversions, sources. Refresh 6hr.
- Buffer integration: GET /1/profiles/{id}/updates/pending and /sent. Refresh 4hr.
- Stripe integration: subscriptions, charges, MRR calculation, trial-to-paid rate, churn. Refresh 4hr.
- APScheduler configuration: register all integrations with their refresh intervals
- Health auto-update: 3 consecutive failures = channel health "warning" + AIInsight generated
- API endpoints: POST /api/metrics/record (for Scotty), POST /api/automations/heartbeat (for Scotty)
- Ad platform integration stubs: Meta, Reddit, Google. Framework ready — implement API calls when keys available.

All integrations must handle: missing API keys (skip gracefully), rate limits, timeouts (10s default), auth failures. Use httpx async with exponential backoff (3 retries).

---

## AFTER PHASE 7 IS CONFIRMED WORKING:

Phase 7 is working. Move to Phase 8: AI Layer + Chat.

Build:
- ai/engine.py: Anthropic API wrapper. System prompt defines MCC's role as marketing operations analyst. Supports tool use (function calling).
- All 8 scheduled AI jobs from Section 8.1. Each writes AIInsight records.
- Execution score calculation (Section 7.1). Displayed on dashboard and daily view.
- AI Chat panel:
  - Slide-out from right edge, 35-40% width, Ctrl+Space toggle
  - Message bubbles: user right, assistant left
  - Full conversation history (ChatConversation + ChatMessage)
  - Tool calling: all tools from Section 8.2. AI calls tools based on conversation context.
  - Page context injection: if Phil is on a specific channel/task/ad page, include that data in context
  - Action confirmation chips: when AI creates a task or records a metric, show linked confirmation
  - Quick action buttons above input: "Morning briefing", "What needs attention?", "Weekly summary"
  - Typing indicator while processing
- Deadline enforcer with dependency chain tracing
- Automation advisor: analyze manual tasks, suggest automations ranked by (time saved/week) / (setup effort)
- Strategic gap analysis: review strategy doc + channels + competitors, flag missing growth levers
- Insight-to-task: each AIInsight action_item has a "Create Task" button that generates a pre-filled task
- Lead score calculation: weekly scoring pass per Section 4.21 rules

---

## AFTER PHASE 8 IS CONFIRMED WORKING:

Phase 8 is working. Move to Phase 9: Strategy + Wizard + Knowledge + Partners.

Build:
- Strategy builder: AI-guided conversation (uses chat interface) across 7 topics (product, customer, competitors, messaging, voice, pillars, budget). Conversation output saved as ProjectStrategy sections. Editable.
- Project wizard (7 steps): Product Definition → Channel Selection → Tool Stack → Milestones → Task Generation → Automation Planning → Review & Launch. AI assists at each step. Task generation uses AI + Grindlab patterns. Output: fully populated project.
- Template system: save project as template, create new project from template.
- Knowledge base: CRUD for KnowledgeEntry. Cross-project search. AI auto-suggest when patterns detected (experiment completes, tool deprecated, anomaly resolved).
- Competitive intelligence: Competitor + CompetitorUpdate CRUD. Comparison table. Monthly review prompts.
- Retention/engagement view: segment distribution (power, active, at_risk, dormant, churned). Trend charts. AI churn prediction insights.
- Win-back: segment calculations from SubscriberEvent. Display in Sequences view as retention-type sequences.
- Partner dashboard: PartnerView CRUD with token generation. Route /partner/{token} renders read-only view with selected components. Presets per Section 16.2 of the original spec.

---

## AFTER PHASE 9 IS CONFIRMED WORKING:

Phase 9 is working. Final phase: Phase 10 — Polish.

1. All keyboard shortcuts from Section 5 (persistent) working
2. Global search: '/' key focuses search, searches all entity types, results grouped by type
3. Cross-links: every entity links to related entities. Channel → tasks, tasks → channel, insight → source, content → channel, automation → channel, etc.
4. Empty states: new blank project shows helpful empty state on every view
5. Loading states: HTMX swap indicators on all partial loads
6. Error states: API failures show user-friendly messages, not stack traces
7. Visual polish: consistent spacing, alignment, color usage across all 22 views
8. Run full testing checklist from Section 13 of the spec
9. Fix anything that fails

When all 37 items in the testing checklist pass, we're done.
