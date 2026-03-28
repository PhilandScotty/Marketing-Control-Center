import enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    Numeric, Float, Enum as SAEnum, ForeignKey, JSON
)
from app.database import Base


# --- Enums ---

class ProjectStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"

class ChannelType(str, enum.Enum):
    email = "email"
    social = "social"
    paid_ads = "paid_ads"
    referral = "referral"
    content = "content"
    community = "community"
    cold_outreach = "cold_outreach"
    seo = "seo"
    partnerships = "partnerships"
    owned = "owned"

class ChannelStatus(str, enum.Enum):
    live = "live"
    planned = "planned"
    building = "building"
    blocked = "blocked"
    paused = "paused"
    deprecated = "deprecated"
    active = "active"

class AutomationLevel(str, enum.Enum):
    full_auto = "full_auto"
    low_touch = "low_touch"
    manual = "manual"

class HealthStatus(str, enum.Enum):
    healthy = "healthy"
    warning = "warning"
    critical = "critical"
    stale = "stale"
    unknown = "unknown"
    good = "good"

class ToolCategory(str, enum.Enum):
    email_marketing = "email_marketing"
    cold_outreach = "cold_outreach"
    analytics = "analytics"
    social_mgmt = "social_mgmt"
    ads_platform = "ads_platform"
    content_production = "content_production"
    automation = "automation"
    referral = "referral"
    payments = "payments"
    hosting = "hosting"
    ai_llm = "ai_llm"
    dev_tools = "dev_tools"
    scraping = "scraping"

class BillingCycle(str, enum.Enum):
    monthly = "monthly"
    annual = "annual"
    one_time = "one_time"
    free = "free"
    usage_based = "usage_based"

class ToolStatus(str, enum.Enum):
    active = "active"
    planned = "planned"
    evaluating = "evaluating"
    deprecated = "deprecated"
    blocked = "blocked"

class TaskStatus(str, enum.Enum):
    backlog = "backlog"
    this_week = "this_week"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    archived = "archived"
    monitoring = "monitoring"
    recurring = "recurring"

class TaskPriority(str, enum.Enum):
    launch_critical = "launch_critical"
    high = "high"
    medium = "medium"
    low = "low"
    cleanup = "cleanup"

class AutomationType(str, enum.Enum):
    cron_job = "cron_job"
    email_sequence = "email_sequence"
    webhook_pipeline = "webhook_pipeline"
    scheduled_post = "scheduled_post"
    referral_program = "referral_program"
    ad_campaign = "ad_campaign"

class AutomationHealth(str, enum.Enum):
    running = "running"
    stale = "stale"
    failed = "failed"
    paused = "paused"
    unknown = "unknown"


class HostingLocation(str, enum.Enum):
    mac_mini = "mac_mini"
    cloud = "cloud"
    hybrid = "hybrid"

class HealthCheckMethod(str, enum.Enum):
    api_poll = "api_poll"
    log_check = "log_check"
    manual_confirm = "manual_confirm"
    webhook_heartbeat = "webhook_heartbeat"

class SequenceType(str, enum.Enum):
    nurture_drip = "nurture_drip"
    broadcast = "broadcast"
    transactional = "transactional"
    triggered = "triggered"
    onboarding = "onboarding"
    retention = "retention"
    win_back = "win_back"

class SequenceStatus(str, enum.Enum):
    live = "live"
    draft = "draft"
    needs_copy = "needs_copy"
    needs_build = "needs_build"
    planned = "planned"
    paused = "paused"

class AdPlatform(str, enum.Enum):
    meta = "meta"
    reddit = "reddit"
    google = "google"
    youtube = "youtube"
    x_twitter = "x_twitter"
    tiktok = "tiktok"

class AdStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    ended = "ended"
    scheduled = "scheduled"
    draft = "draft"

class AdObjective(str, enum.Enum):
    traffic = "traffic"
    conversions = "conversions"
    awareness = "awareness"
    retargeting = "retargeting"
    engagement = "engagement"

class AdSignal(str, enum.Enum):
    scale = "scale"
    hold = "hold"
    optimize = "optimize"
    pause = "pause"
    kill = "kill"

class ContentType(str, enum.Enum):
    short_video = "short_video"
    long_video = "long_video"
    text_post = "text_post"
    thread = "thread"
    blog = "blog"
    email = "email"
    graphic = "graphic"

class ProductionLane(str, enum.Enum):
    lane1_text_motion = "lane1_text_motion"
    lane2_raw_capture = "lane2_raw_capture"
    lane3_selfie = "lane3_selfie"
    lane4_produced = "lane4_produced"

class ContentStatus(str, enum.Enum):
    concept = "concept"
    scripted = "scripted"
    filmed = "filmed"
    with_editor = "with_editor"
    edited = "edited"
    scheduled = "scheduled"
    published = "published"

class MetricSource(str, enum.Enum):
    api = "api"
    manual = "manual"

class InsightType(str, enum.Enum):
    anomaly = "anomaly"
    deadline_warning = "deadline_warning"
    dependency_risk = "dependency_risk"
    stale_automation = "stale_automation"
    ad_signal = "ad_signal"
    suggestion = "suggestion"
    trend = "trend"
    gap_analysis = "gap_analysis"
    weekly_digest = "weekly_digest"
    bottleneck = "bottleneck"
    experiment_result = "experiment_result"

class InsightSourceType(str, enum.Enum):
    channel = "channel"
    task = "task"
    automation = "automation"
    ad_campaign = "ad_campaign"
    tool = "tool"
    sequence = "sequence"
    content = "content"
    subscriber = "subscriber"
    onboarding = "onboarding"
    general = "general"

class InsightSeverity(str, enum.Enum):
    info = "info"
    attention = "attention"
    urgent = "urgent"
    critical = "critical"

class ContactType(str, enum.Enum):
    influencer = "influencer"
    coach = "coach"
    ambassador_prospect = "ambassador_prospect"
    affiliate_prospect = "affiliate_prospect"
    partnership = "partnership"

class ContactStatus(str, enum.Enum):
    identified = "identified"
    contacted = "contacted"
    responded = "responded"
    in_conversation = "in_conversation"
    committed = "committed"
    active = "active"
    declined = "declined"
    ghosted = "ghosted"

class QueueItemType(str, enum.Enum):
    outreach_followup = "outreach_followup"
    outreach_decline_check = "outreach_decline_check"
    outreach_checkin = "outreach_checkin"
    content_draft = "content_draft"
    content_suggestion = "content_suggestion"
    ai_recommendation = "ai_recommendation"
    discovered_prospect = "discovered_prospect"

class QueueItemStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited = "edited"
    skipped = "skipped"
    rejected = "rejected"

class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"

class SubscriberStage(str, enum.Enum):
    waitlist_lead = "waitlist_lead"
    free_trial_active = "free_trial_active"
    free_trial_expired = "free_trial_expired"
    paid_basic = "paid_basic"
    paid_premium = "paid_premium"
    churned = "churned"
    paused = "paused"

class SubscriberEventType(str, enum.Enum):
    trial_start = "trial_start"
    trial_expire = "trial_expire"
    convert_basic = "convert_basic"
    convert_premium = "convert_premium"
    churn = "churn"
    pause = "pause"
    reactivate = "reactivate"

class TagDimension(str, enum.Enum):
    hook_type = "hook_type"
    topic = "topic"
    pillar = "pillar"
    tone = "tone"
    format = "format"
    cta_type = "cta_type"
    audience = "audience"

class StrategySection(str, enum.Enum):
    product = "product"
    customer = "customer"
    competitors = "competitors"
    messaging = "messaging"
    voice = "voice"
    pillars = "pillars"
    budget = "budget"

class BudgetCategory(str, enum.Enum):
    tools_services = "tools_services"
    paid_advertising = "paid_advertising"
    content_production = "content_production"
    lead_acquisition = "lead_acquisition"
    events_travel = "events_travel"
    reserve = "reserve"
    other = "other"

class ExpenseSource(str, enum.Enum):
    auto = "auto"
    manual = "manual"

class CompetitorUpdateType(str, enum.Enum):
    pricing_change = "pricing_change"
    feature_launch = "feature_launch"
    content_observed = "content_observed"
    partnership = "partnership"
    funding = "funding"
    other = "other"

class KnowledgeEntryType(str, enum.Enum):
    lesson = "lesson"
    tool_decision = "tool_decision"
    playbook = "playbook"
    benchmark = "benchmark"
    pattern = "pattern"

class ExperimentTestType(str, enum.Enum):
    email_subject = "email_subject"
    landing_page = "landing_page"
    ad_creative = "ad_creative"
    content_hook = "content_hook"
    cta_placement = "cta_placement"
    pricing = "pricing"

class ExperimentStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    complete = "complete"
    inconclusive = "inconclusive"

class ExperimentWinner(str, enum.Enum):
    a = "a"
    b = "b"
    inconclusive = "inconclusive"

class LeadTier(str, enum.Enum):
    hot = "hot"
    warm = "warm"
    cool = "cool"
    cold = "cold"

class FeedbackSource(str, enum.Enum):
    email = "email"
    survey = "survey"
    social = "social"
    support = "support"
    exit_survey = "exit_survey"
    manual = "manual"

class FeedbackType(str, enum.Enum):
    testimonial = "testimonial"
    feature_request = "feature_request"
    complaint = "complaint"
    nps = "nps"
    cancellation_reason = "cancellation_reason"
    use_case = "use_case"

class Sentiment(str, enum.Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


# --- Models ---

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), nullable=False, unique=True)
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.active)
    launch_date = Column(Date, nullable=True)
    monthly_budget = Column(Numeric(10, 2), default=0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    channel_type = Column(SAEnum(ChannelType), nullable=False)
    status = Column(SAEnum(ChannelStatus), default=ChannelStatus.planned)
    automation_level = Column(SAEnum(AutomationLevel), default=AutomationLevel.manual)
    owner = Column(String(50), default="phil")
    integration_key = Column(String(50), nullable=True)
    health = Column(SAEnum(HealthStatus), default=HealthStatus.unknown)
    health_reason = Column(String(500), nullable=True)
    daily_actions = Column(JSON, default=list)
    auto_actions = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)
    attributed_mrr = Column(Numeric(10, 2), nullable=True)
    total_spend_to_date = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tool(Base):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(SAEnum(ToolCategory), nullable=False)
    purpose = Column(String(500), default="")
    monthly_cost = Column(Numeric(10, 2), default=0)
    billing_cycle = Column(SAEnum(BillingCycle), default=BillingCycle.monthly)
    status = Column(SAEnum(ToolStatus), default=ToolStatus.active)
    blocker = Column(String(500), nullable=True)
    api_integrated = Column(Boolean, default=False)
    api_key_env_var = Column(String(100), nullable=True)
    alternative_to = Column(Integer, ForeignKey("tools.id"), nullable=True)
    gap_flag = Column(Boolean, default=False)
    redundancy_flag = Column(Boolean, default=False)
    last_reviewed = Column(Date, default=date.today)
    notes = Column(Text, default="")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(SAEnum(TaskStatus), default=TaskStatus.backlog)
    priority = Column(SAEnum(TaskPriority), default=TaskPriority.medium)
    assigned_to = Column(String(50), default="phil")
    due_date = Column(Date, nullable=True)
    start_date = Column(Date, nullable=True)
    estimated_hours = Column(Float, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    blocked_by = Column(JSON, default=list)
    blocks = Column(JSON, default=list)
    recurring_schedule = Column(String(100), nullable=True)
    recurring_frequency = Column(String(20), nullable=True)  # daily, weekly, biweekly, monthly
    recurring_next_due = Column(Date, nullable=True)
    monitoring_metric = Column(String(100), nullable=True)
    monitoring_threshold = Column(String(100), nullable=True)
    escalation_hours = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    name = Column(String(200), nullable=False)
    automation_type = Column(SAEnum(AutomationType), nullable=False)
    platform = Column(String(100), default="")
    schedule = Column(String(200), nullable=True)
    expected_run_interval_hours = Column(Integer, nullable=True)
    last_confirmed_run = Column(DateTime, nullable=True)
    health = Column(SAEnum(AutomationHealth), default=AutomationHealth.unknown)
    health_check_method = Column(SAEnum(HealthCheckMethod), default=HealthCheckMethod.manual_confirm)
    health_check_config = Column(JSON, default=dict)
    owner = Column(String(50), default="phil")
    script_path = Column(String(500), nullable=True)
    hosting = Column(SAEnum(HostingLocation), default=HostingLocation.mac_mini)
    notes = Column(Text, default="")


class EmailSequence(Base):
    __tablename__ = "email_sequences"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    sequence_type = Column(SAEnum(SequenceType), nullable=False)
    platform = Column(String(100), default="")
    email_count = Column(Integer, default=0)
    status = Column(SAEnum(SequenceStatus), default=SequenceStatus.planned)
    trigger = Column(String(500), default="")
    open_rate = Column(Numeric(5, 2), nullable=True)
    click_rate = Column(Numeric(5, 2), nullable=True)
    subscribers_active = Column(Integer, nullable=True)
    last_reviewed = Column(Date, nullable=True)
    notes = Column(Text, default="")


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    platform = Column(SAEnum(AdPlatform), nullable=False)
    campaign_name = Column(String(200), nullable=False)
    campaign_id_external = Column(String(200), nullable=True)
    status = Column(SAEnum(AdStatus), default=AdStatus.draft)
    objective = Column(SAEnum(AdObjective), default=AdObjective.traffic)
    daily_budget = Column(Numeric(10, 2), default=0)
    total_budget = Column(Numeric(10, 2), nullable=True)
    spend_to_date = Column(Numeric(10, 2), default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Numeric(5, 2), default=0)
    conversions = Column(Integer, default=0)
    cpl = Column(Numeric(10, 2), nullable=True)
    roas = Column(Numeric(10, 2), nullable=True)
    cpm = Column(Numeric(10, 2), nullable=True)
    signal = Column(SAEnum(AdSignal), default=AdSignal.hold)
    signal_reason = Column(String(500), nullable=True)
    creative_notes = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    notes = Column(Text, default="")


class CampaignCore(Base):
    __tablename__ = "campaign_cores"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    display_name = Column(String(200), nullable=False)
    objective = Column(String(100), nullable=False)
    offer = Column(String(150), nullable=False)
    audience = Column(String(150), default="")
    theme = Column(String(150), default="")
    period = Column(String(50), nullable=False)
    campaign_slug = Column(String(250), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrackedLink(Base):
    __tablename__ = "tracked_links"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    campaign_core_id = Column(Integer, ForeignKey("campaign_cores.id"), nullable=True)
    owner = Column(String(50), default="phil")
    channel = Column(String(100), default="")
    base_url = Column(String(500), nullable=False)
    final_url = Column(String(1200), nullable=False)
    utm_source = Column(String(100), nullable=False)
    utm_medium = Column(String(100), nullable=False)
    utm_campaign = Column(String(200), nullable=False)
    utm_content = Column(String(200), nullable=False)
    utm_term = Column(String(200), default="")
    utm_id = Column(String(200), default="")
    placement = Column(String(200), default="")
    qa_status = Column(String(50), default="draft")
    qa_approved_by = Column(String(100), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ContentPiece(Base):
    __tablename__ = "content_pieces"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(300), nullable=False)
    series = Column(String(200), default="")
    content_type = Column(SAEnum(ContentType), nullable=False)
    production_lane = Column(SAEnum(ProductionLane), default=ProductionLane.lane1_text_motion)
    status = Column(SAEnum(ContentStatus), default=ContentStatus.concept)
    assigned_to = Column(String(50), default="phil")
    platform_target = Column(JSON, default=list)
    script_source = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    published_at = Column(DateTime, nullable=True)
    published_urls = Column(JSON, default=dict)
    performance = Column(JSON, nullable=True)
    notes = Column(Text, default="")


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(12, 2), nullable=False)
    previous_value = Column(Numeric(12, 2), nullable=True)
    unit = Column(String(50), default="count")
    source = Column(SAEnum(MetricSource), default=MetricSource.manual)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value = Column(Numeric(12, 2), nullable=False)
    snapshot_date = Column(Date, default=date.today)


class AIInsight(Base):
    __tablename__ = "ai_insights"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    insight_type = Column(SAEnum(InsightType), nullable=False)
    source_type = Column(SAEnum(InsightSourceType), nullable=False)
    source_id = Column(Integer, nullable=True)
    title = Column(String(300), nullable=False)
    body = Column(Text, default="")
    severity = Column(SAEnum(InsightSeverity), default=InsightSeverity.info)
    action_items = Column(JSON, default=list)
    why_it_matters = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    fix_url = Column(String(500), nullable=True)
    needs_clint = Column(Boolean, default=False)
    acknowledged = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OutreachContact(Base):
    __tablename__ = "outreach_contacts"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=False)
    audience_size = Column(Integer, nullable=True)
    contact_type = Column(SAEnum(ContactType), default=ContactType.influencer)
    status = Column(SAEnum(ContactStatus), default=ContactStatus.identified)
    last_contact_date = Column(Date, nullable=True)
    next_follow_up = Column(Date, nullable=True)
    outreach_stage = Column(Integer, default=1)
    commission_tier = Column(String(100), nullable=True)
    referral_link = Column(String(500), nullable=True)
    notes = Column(Text, default="")
    contact_email = Column(String(300), nullable=True)
    twitter_handle = Column(String(200), nullable=True)
    instagram_handle = Column(String(200), nullable=True)
    website_url = Column(String(500), nullable=True)
    youtube_channel = Column(String(300), nullable=True)
    outreach_log = Column(Text, default="")
    is_discovered = Column(Boolean, default=False)
    discovered_at = Column(DateTime, nullable=True)
    discovery_source = Column(String(100), nullable=True)  # youtube_api, web_search, etc.
    stage_changed_at = Column(DateTime, nullable=True)
    followup_drafted_at = Column(DateTime, nullable=True)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(200), default="New Chat")
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False)
    role = Column(SAEnum(ChatRole), nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PartnerView(Base):
    __tablename__ = "partner_views"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    token = Column(String(100), nullable=False, unique=True)
    preset = Column(String(50), default="full_readonly")
    custom_config = Column(JSON, default=dict)
    banner_text = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    last_accessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberSnapshot(Base):
    __tablename__ = "subscriber_snapshots"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    stage = Column(SAEnum(SubscriberStage), nullable=False)
    count = Column(Integer, default=0)
    mrr = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriberEvent(Base):
    __tablename__ = "subscriber_events"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    email_hash = Column(String(64), nullable=False)
    event_type = Column(SAEnum(SubscriberEventType), nullable=False)
    source_channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)


class ContentTag(Base):
    __tablename__ = "content_tags"
    id = Column(Integer, primary_key=True)
    content_piece_id = Column(Integer, ForeignKey("content_pieces.id"), nullable=True)
    email_sequence_id = Column(Integer, ForeignKey("email_sequences.id"), nullable=True)
    ad_campaign_id = Column(Integer, ForeignKey("ad_campaigns.id"), nullable=True)
    outreach_id = Column(Integer, ForeignKey("outreach_contacts.id"), nullable=True)
    tag_dimension = Column(SAEnum(TagDimension), nullable=False)
    tag_value = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PerformanceScore(Base):
    __tablename__ = "performance_scores"
    id = Column(Integer, primary_key=True)
    content_piece_id = Column(Integer, ForeignKey("content_pieces.id"), nullable=True)
    email_sequence_id = Column(Integer, ForeignKey("email_sequences.id"), nullable=True)
    ad_campaign_id = Column(Integer, ForeignKey("ad_campaigns.id"), nullable=True)
    platform = Column(String(100), nullable=False)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    engagement_score = Column(Numeric(10, 2), default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class ProjectStrategy(Base):
    __tablename__ = "project_strategies"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    section = Column(SAEnum(StrategySection), nullable=False)
    content = Column(Text, default="")
    ai_conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BudgetAllocation(Base):
    __tablename__ = "budget_allocations"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    category = Column(SAEnum(BudgetCategory), nullable=False)
    planned_monthly = Column(Numeric(10, 2), default=0)
    period_start = Column(Date, nullable=False)
    notes = Column(Text, default="")


class BudgetExpense(Base):
    __tablename__ = "budget_expenses"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    category = Column(SAEnum(BudgetCategory), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(500), default="")
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=True)
    ad_campaign_id = Column(Integer, ForeignKey("ad_campaigns.id"), nullable=True)
    expense_date = Column(Date, nullable=False)
    source = Column(SAEnum(ExpenseSource), default=ExpenseSource.manual)


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(SAEnum(BudgetCategory), default=BudgetCategory.tools_services)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=True)
    is_recurring = Column(Boolean, default=True)
    default_amount = Column(Numeric(10, 2), default=0)
    first_month = Column(Date, nullable=False)
    ended_month = Column(Date, nullable=True)
    custom_category_name = Column(String(100), nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class BudgetMonthEntry(Base):
    __tablename__ = "budget_month_entries"
    id = Column(Integer, primary_key=True)
    line_item_id = Column(Integer, ForeignKey("budget_line_items.id"), nullable=False)
    month = Column(Date, nullable=False)  # always 1st of month
    budgeted = Column(Numeric(10, 2), default=0)
    actual = Column(Numeric(10, 2), default=0)
    auto_filled = Column(Boolean, default=False)
    auto_filled_at = Column(DateTime, nullable=True)


class MonthlyRevenue(Base):
    __tablename__ = "monthly_revenue"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    month = Column(Date, nullable=False)
    mrr = Column(Numeric(10, 2), default=0)
    new_subscribers = Column(Integer, default=0)
    churned_subscribers = Column(Integer, default=0)
    total_subscribers = Column(Integer, default=0)


class Competitor(Base):
    __tablename__ = "competitors"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    website = Column(String(500), default="")
    pricing_summary = Column(Text, default="")
    positioning_summary = Column(Text, default="")
    strengths = Column(Text, default="")
    weaknesses = Column(Text, default="")
    key_channels = Column(JSON, default=list)
    last_checked = Column(Date, default=date.today)
    notes = Column(Text, default="")


class CompetitorUpdate(Base):
    __tablename__ = "competitor_updates"
    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False)
    update_type = Column(SAEnum(CompetitorUpdateType), nullable=False)
    summary = Column(Text, default="")
    source_url = Column(String(500), nullable=True)
    observed_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), default="phil")


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    entry_type = Column(SAEnum(KnowledgeEntryType), nullable=False)
    title = Column(String(300), nullable=False)
    body = Column(Text, default="")
    tags = Column(JSON, default=list)
    source_project = Column(String(100), default="")
    source_conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=True)
    auto_generated = Column(Boolean, default=False)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    hypothesis = Column(Text, nullable=False)
    test_type = Column(SAEnum(ExperimentTestType), nullable=False)
    variant_a = Column(Text, default="")
    variant_b = Column(Text, default="")
    success_metric = Column(String(200), default="")
    sample_target = Column(Integer, nullable=True)
    duration_days = Column(Integer, nullable=True)
    status = Column(SAEnum(ExperimentStatus), default=ExperimentStatus.draft)
    winner = Column(SAEnum(ExperimentWinner), nullable=True)
    result_summary = Column(Text, nullable=True)
    decision = Column(Text, nullable=True)
    knowledge_entry_id = Column(Integer, ForeignKey("knowledge_entries.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LeadScore(Base):
    __tablename__ = "lead_scores"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    email_hash = Column(String(64), nullable=False)
    current_score = Column(Integer, default=0)
    tier = Column(SAEnum(LeadTier), default=LeadTier.cold)
    source_channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    scoring_events = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerFeedback(Base):
    __tablename__ = "customer_feedback"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source = Column(SAEnum(FeedbackSource), nullable=False)
    feedback_type = Column(SAEnum(FeedbackType), nullable=False)
    content = Column(Text, nullable=False)
    sentiment = Column(SAEnum(Sentiment), default=Sentiment.neutral)
    themes = Column(JSON, default=list)
    can_use_publicly = Column(Boolean, default=False)
    customer_identifier = Column(String(64), nullable=True)
    nps_score = Column(Integer, nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OnboardingMilestone(Base):
    __tablename__ = "onboarding_milestones"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    target_days_from_start = Column(Integer, default=1)
    display_order = Column(Integer, default=0)
    intervention_sequence_id = Column(Integer, ForeignKey("email_sequences.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AutonomousToolType(str, enum.Enum):
    bot = "bot"
    cron_system = "cron_system"
    webhook_pipeline = "webhook_pipeline"
    monitoring = "monitoring"
    scraper = "scraper"
    other = "other"


class AutonomousToolHealth(str, enum.Enum):
    online = "online"
    degraded = "degraded"
    offline = "offline"
    unknown = "unknown"


class AutonomousTool(Base):
    __tablename__ = "autonomous_tools"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    tool_type = Column(SAEnum(AutonomousToolType), default=AutonomousToolType.bot)
    platform = Column(String(200), default="")
    workspace_path = Column(String(500), nullable=True)
    api_endpoint = Column(String(500), nullable=True)
    expected_heartbeat_hours = Column(Integer, nullable=True)
    owner = Column(String(50), default="phil")
    notes = Column(Text, default="")
    api_key = Column(String(64), nullable=False, unique=True)
    health = Column(SAEnum(AutonomousToolHealth), default=AutonomousToolHealth.unknown)
    last_heartbeat = Column(DateTime, nullable=True)
    last_heartbeat_message = Column(String(500), nullable=True)
    total_heartbeats = Column(Integer, default=0)
    total_metrics = Column(Integer, default=0)
    total_alerts = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToolMetricLog(Base):
    __tablename__ = "tool_metric_logs"
    id = Column(Integer, primary_key=True)
    tool_id = Column(Integer, ForeignKey("autonomous_tools.id"), nullable=False)
    metric_name = Column(String(200), nullable=False)
    metric_value = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(50), default="count")
    context = Column(JSON, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class ToolAlert(Base):
    __tablename__ = "tool_alerts"
    id = Column(Integer, primary_key=True)
    tool_id = Column(Integer, ForeignKey("autonomous_tools.id"), nullable=False)
    severity = Column(SAEnum(InsightSeverity), default=InsightSeverity.info)
    title = Column(String(300), nullable=False)
    body = Column(Text, default="")
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    subscriber_hash = Column(String(64), nullable=False)
    milestone_id = Column(Integer, ForeignKey("onboarding_milestones.id"), nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    intervention_sent = Column(Boolean, default=False)
    intervention_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# --- Feature 1: Checklist Items ---

class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String(300), nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    sort_order = Column(Integer, default=0)


# --- Feature 3: Launch Templates ---

class LaunchTemplate(Base):
    __tablename__ = "launch_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    created_from_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TemplateTask(Base):
    __tablename__ = "template_tasks"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("launch_templates.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    relative_day = Column(Integer, default=0)
    priority = Column(SAEnum(TaskPriority), default=TaskPriority.medium)
    assigned_role = Column(String(50), default="founder")
    channel_type = Column(String(50), nullable=True)
    checklist_items = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)


# --- Feature 4: Brand Assets ---

class BrandColor(Base):
    __tablename__ = "brand_colors"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    hex_code = Column(String(7), nullable=False)
    usage_notes = Column(String(300), default="")
    sort_order = Column(Integer, default=0)


class BrandFont(Base):
    __tablename__ = "brand_fonts"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    usage = Column(String(100), default="")
    font_url = Column(String(500), nullable=True)
    sort_order = Column(Integer, default=0)


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    asset_type = Column(String(50), nullable=False)  # logo, banner, other
    name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=True)
    dimensions = Column(String(50), nullable=True)
    platform = Column(String(100), nullable=True)
    usage_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class PlatformProfile(Base):
    __tablename__ = "platform_profiles"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    platform = Column(String(100), nullable=False)
    handle = Column(String(200), nullable=False)
    profile_url = Column(String(500), default="")
    bio_text = Column(Text, default="")
    profile_pic_asset_id = Column(Integer, ForeignKey("brand_assets.id"), nullable=True)
    banner_asset_id = Column(Integer, ForeignKey("brand_assets.id"), nullable=True)
    link = Column(String(500), default="")
    sort_order = Column(Integer, default=0)


class BrandGuidelines(Base):
    __tablename__ = "brand_guidelines"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    voice_rules = Column(Text, default="")
    banned_words = Column(Text, default="")
    tone_description = Column(Text, default="")
    content_mix = Column(Text, default="")
    notes = Column(Text, default="")


class IntelItemType(str, enum.Enum):
    channel_discovery = "channel_discovery"
    tool_discovery = "tool_discovery"
    landscape = "landscape"


class IntelItemStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    accepted = "accepted"
    dismissed = "dismissed"


class LandscapeCategory(str, enum.Enum):
    competitor = "competitor"
    platform = "platform"
    industry = "industry"
    trend = "trend"


class LandscapeUrgency(str, enum.Enum):
    act_now = "act_now"
    act_this_week = "act_this_week"
    awareness = "awareness"


class IntelligenceItem(Base):
    """Unified table for all three intelligence tabs."""
    __tablename__ = "intelligence_items"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    item_type = Column(SAEnum(IntelItemType), nullable=False)
    status = Column(SAEnum(IntelItemStatus), default=IntelItemStatus.new)

    # Shared fields
    title = Column(String(300), nullable=False)
    body = Column(Text, default="")
    fit_score = Column(Integer, nullable=True)  # 1-10 for channel/tool discovery

    # Channel discovery fields
    time_per_week = Column(String(100), nullable=True)
    cost_per_month = Column(String(100), nullable=True)
    timeline_to_results = Column(String(200), nullable=True)
    risk_downside = Column(Text, nullable=True)

    # Tool discovery fields
    replaces_tool = Column(String(200), nullable=True)
    tool_cost = Column(String(100), nullable=True)
    net_cost_impact = Column(String(200), nullable=True)
    integration_complexity = Column(String(100), nullable=True)
    confidence_level = Column(String(100), nullable=True)
    tool_category = Column(String(100), nullable=True)

    # Landscape monitor fields
    landscape_category = Column(SAEnum(LandscapeCategory), nullable=True)
    urgency = Column(SAEnum(LandscapeUrgency), nullable=True)
    source_url = Column(String(500), nullable=True)
    action_recommended = Column(Text, nullable=True)

    # Not-recommended section (channel/tool discovery)
    is_not_recommended = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)

    # Dismiss tracking
    dismiss_reason = Column(String(500), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebsiteAnalysis(Base):
    __tablename__ = "website_analyses"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    snapshot_data = Column(JSON, default=dict)  # traffic/funnel/sources at time of analysis
    sections = Column(JSON, default=dict)  # 7 analysis sections from AI
    total_recommendations = Column(Integer, default=0)
    high_impact_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebsiteRecommendation(Base):
    __tablename__ = "website_recommendations"
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey("website_analyses.id"), nullable=False)
    section = Column(String(100), nullable=False)  # traffic_diagnosis, missing_sources, etc.
    headline = Column(String(300), nullable=False)
    body = Column(Text, default="")
    assignee = Column(String(50), default="phil")
    estimated_time = Column(String(100), default="")
    expected_impact = Column(String(200), default="")
    impact_level = Column(String(20), default="medium")  # high, medium, low
    difficulty = Column(String(20), default="medium")  # easy, medium, hard
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    followed = Column(Boolean, default=False)
    impact_result = Column(Text, nullable=True)  # auto-filled after 30 days
    created_at = Column(DateTime, default=datetime.utcnow)


class HeatmapInsight(Base):
    __tablename__ = "heatmap_insights"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    insight_date = Column(Date, nullable=False)
    page = Column(String(200), nullable=False)
    observation = Column(Text, nullable=False)
    action_taken = Column(Text, default="")
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MorningBrief(Base):
    __tablename__ = "morning_briefs"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    brief_date = Column(Date, nullable=False)
    priorities = Column(JSON, default=list)  # top 3 priorities [{title, body, urgency}]
    snapshot = Column(JSON, default=dict)     # full data snapshot used to generate
    raw_response = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DismissedProspect(Base):
    __tablename__ = "dismissed_prospects"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=False)
    youtube_channel_id = Column(String(100), nullable=True)
    external_id = Column(String(200), nullable=True)  # any platform-specific ID
    dismissed_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(String(300), default="Auto-discovered -- dismissed")


class ApprovalQueueItem(Base):
    __tablename__ = "approval_queue"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    item_type = Column(SAEnum(QueueItemType), nullable=False)
    status = Column(SAEnum(QueueItemStatus), default=QueueItemStatus.pending)
    source_label = Column(String(100), nullable=False)  # e.g. "Outreach", "AI", "Discovery"
    title = Column(String(300), nullable=False)
    preview = Column(Text, default="")
    draft_message = Column(Text, nullable=True)  # editable draft (for follow-ups)
    contact_id = Column(Integer, ForeignKey("outreach_contacts.id"), nullable=True)
    insight_id = Column(Integer, ForeignKey("ai_insights.id"), nullable=True)
    action_url = Column(String(500), nullable=True)  # link to relevant page
    content_pillar = Column(String(100), nullable=True)  # content draft metadata
    content_platform = Column(String(50), nullable=True)
    content_series = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    acted_at = Column(DateTime, nullable=True)


class AdBrief(Base):
    __tablename__ = "ad_briefs"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    platform = Column(SAEnum(AdPlatform), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=True)
    title = Column(String(300), nullable=False)
    creative_text = Column(Text, default="")
    targeting_notes = Column(Text, default="")
    recommended_budget = Column(Numeric(10, 2), default=0)
    suggested_duration_days = Column(Integer, default=14)
    source_post_data = Column(JSON, nullable=True)  # top organic posts used as reference
    customer_profile_ref = Column(Text, nullable=True)
    budget_line_item_id = Column(Integer, ForeignKey("budget_line_items.id"), nullable=True)
    status = Column(String(20), default="draft")  # draft, active, completed
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
