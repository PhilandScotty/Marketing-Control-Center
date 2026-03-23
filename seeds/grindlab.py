import uuid
from datetime import date, datetime
from app.models import (
    Project, Channel, Tool, Task, Automation, EmailSequence,
    Competitor, OutreachContact, OnboardingMilestone, Metric,
    AdCampaign,
    AutonomousTool, AutonomousToolType, AutonomousToolHealth,
    HostingLocation,
    ChannelType, ChannelStatus, AutomationLevel, HealthStatus,
    ToolCategory, BillingCycle, ToolStatus,
    TaskStatus, TaskPriority,
    AutomationType, AutomationHealth, HealthCheckMethod,
    SequenceType, SequenceStatus,
    ContactType, ContactStatus,
    MetricSource,
    AdPlatform, AdStatus, AdObjective, AdSignal,
    BrandColor, BrandFont, PlatformProfile, BrandGuidelines,
    LaunchTemplate, TemplateTask,
)


def seed_grindlab(db):
    existing = db.query(Project).filter_by(slug="grindlab").first()
    if existing:
        return

    # --- Project ---
    project = Project(
        name="Grindlab",
        slug="grindlab",
        status="active",
        launch_date=date(2026, 4, 1),
        monthly_budget=1500,
        notes="Poker study SaaS - grindlab.ai. First MCC project.",
    )
    db.add(project)
    db.flush()
    pid = project.id

    # --- Channels (14) ---
    channels_data = [
        {"name": "Email Nurture (Kit)", "channel_type": ChannelType.email, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.full_auto, "integration_key": "convertkit",
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Check open rates", "Review new subscriber tags"],
         "auto_actions": ["Nurture drip sends automatically", "Tag-based segmentation"]},

        {"name": "Cold Email (Instantly)", "channel_type": ChannelType.cold_outreach, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.full_auto, "integration_key": "instantly",
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Check reply rate", "Review positive replies", "Audit bounce rate"],
         "auto_actions": ["Warmup runs continuously", "Sequences send on schedule"]},

        {"name": "Leak Finder Quiz", "channel_type": ChannelType.content, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.full_auto, "integration_key": "ga4",
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Check completion rate"],
         "auto_actions": ["Quiz auto-scores", "Results email via n8n pipeline", "Adds to Kit nurture"]},

        {"name": "Reddit Engagement", "channel_type": ChannelType.community, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.low_touch, "integration_key": None,
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Post in r/poker", "Engage with comments", "Share Leak Finder when relevant"],
         "auto_actions": ["Reddit Daily Brief cron (7AM)"]},

        {"name": "X/Twitter", "channel_type": ChannelType.social, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.low_touch, "integration_key": "buffer",
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Queue posts in Buffer", "Engage with poker Twitter"],
         "auto_actions": ["Buffer auto-posts from queue"]},

        {"name": "Instagram", "channel_type": ChannelType.social, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.low_touch, "integration_key": "buffer",
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Post reels/stories", "Engage with poker IG"],
         "auto_actions": ["Buffer auto-posts from queue"]},

        {"name": "YouTube", "channel_type": ChannelType.content, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.healthy, "owner": "karen",
         "daily_actions": ["Review Karen's edits", "Approve uploads"],
         "auto_actions": []},

        {"name": "SparkLoop Referral", "channel_type": ChannelType.referral, "status": ChannelStatus.live,
         "automation_level": AutomationLevel.full_auto, "integration_key": None,
         "health": HealthStatus.healthy, "owner": "phil",
         "daily_actions": ["Check referral counts"],
         "auto_actions": ["SparkLoop tracks referrals", "Reward tiers auto-applied"]},

        {"name": "Influencer Outreach", "channel_type": ChannelType.partnerships, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": ["Identify targets", "Send DMs", "Follow up"],
         "auto_actions": []},

        {"name": "TikTok", "channel_type": ChannelType.social, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": ["Post short-form content"],
         "auto_actions": []},

        {"name": "Rumble", "channel_type": ChannelType.content, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": ["Cross-post YouTube content"],
         "auto_actions": []},

        {"name": "Paid Ads", "channel_type": ChannelType.paid_ads, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": ["Monitor spend and CPL", "Adjust targeting"],
         "auto_actions": []},

        {"name": "Ambassador Program", "channel_type": ChannelType.partnerships, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": [],
         "auto_actions": []},

        {"name": "Affiliate Program", "channel_type": ChannelType.partnerships, "status": ChannelStatus.planned,
         "automation_level": AutomationLevel.manual, "integration_key": None,
         "health": HealthStatus.unknown, "owner": "phil",
         "daily_actions": [],
         "auto_actions": []},
    ]

    channel_objs = {}
    for cd in channels_data:
        ch = Channel(project_id=pid, **cd)
        db.add(ch)
        db.flush()
        channel_objs[cd["name"]] = ch

    # --- Tools (17) ---
    tools_data = [
        {"name": "ConvertKit", "category": ToolCategory.email_marketing, "purpose": "Email list management, nurture sequences, tagging",
         "monthly_cost": 79, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.active,
         "api_integrated": True, "api_key_env_var": "CONVERTKIT_API_SECRET"},
        {"name": "Instantly", "category": ToolCategory.cold_outreach, "purpose": "Cold email warmup and sending",
         "monthly_cost": 97, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.active,
         "api_integrated": True, "api_key_env_var": "INSTANTLY_API_KEY"},
        {"name": "Railway", "category": ToolCategory.automation, "purpose": "n8n workflow hosting for pipelines",
         "monthly_cost": 5, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.active,
         "api_integrated": True, "api_key_env_var": "RAILWAY_API_KEY"},
        {"name": "Resend", "category": ToolCategory.email_marketing, "purpose": "Transactional email delivery",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Buffer", "category": ToolCategory.social_mgmt, "purpose": "Social media post scheduling",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": True, "api_key_env_var": "BUFFER_ACCESS_TOKEN"},
        {"name": "X Premium", "category": ToolCategory.social_mgmt, "purpose": "Twitter/X premium features",
         "monthly_cost": 4, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "SparkLoop", "category": ToolCategory.referral, "purpose": "Newsletter referral program",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False, "api_key_env_var": "SPARKLOOP_API_KEY"},
        {"name": "OpenRouter", "category": ToolCategory.ai_llm, "purpose": "LLM API access for content generation",
         "monthly_cost": 0.09, "billing_cycle": BillingCycle.usage_based, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "GA4", "category": ToolCategory.analytics, "purpose": "Website analytics and conversion tracking",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": True, "api_key_env_var": "GA4_CREDENTIALS_PATH"},
        {"name": "GTM", "category": ToolCategory.analytics, "purpose": "Tag management for tracking pixels",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Meta Pixel", "category": ToolCategory.ads_platform, "purpose": "Facebook/Instagram ad tracking pixel",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Hotjar", "category": ToolCategory.analytics, "purpose": "Heatmaps and session recordings",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Karen (Editor)", "category": ToolCategory.content_production, "purpose": "Video editing for YouTube and social content",
         "monthly_cost": 800, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Vercel", "category": ToolCategory.hosting, "purpose": "Frontend hosting for grindlab.ai",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Supabase", "category": ToolCategory.hosting, "purpose": "Backend database and auth for Grindlab app",
         "monthly_cost": 0, "billing_cycle": BillingCycle.free, "status": ToolStatus.active,
         "api_integrated": False},
        {"name": "Rewardful", "category": ToolCategory.referral, "purpose": "Affiliate program management",
         "monthly_cost": 49, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.planned,
         "api_integrated": False},
        {"name": "Phantombuster", "category": ToolCategory.scraping, "purpose": "Social media scraping for lead generation",
         "monthly_cost": 69, "billing_cycle": BillingCycle.monthly, "status": ToolStatus.planned,
         "api_integrated": False},
    ]

    for td in tools_data:
        db.add(Tool(project_id=pid, **td))

    # --- Tasks (40+) ---
    tasks_data = [
        # Launch Critical
        {"title": "Launch countdown email sequence", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 23),
         "description": "Build 6-8 email countdown sequence in ConvertKit for launch day"},
        {"title": "Trial expiration flow", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 28),
         "description": "3-email sequence triggered when free trial expires"},
        {"title": "Onboarding activation email", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 28),
         "description": "Welcome email with first steps after signup"},
        {"title": "Cancellation/pause flow spec", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 25),
         "description": "Define cancellation and pause flow with exit survey"},
        {"title": "Purchase page copy", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 20),
         "description": "Write copy for the purchase/pricing page"},
        {"title": "Website strategy decision", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 10),
         "description": "Decide on website architecture and tech approach"},
        {"title": "Cold email angle audit", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 12),
         "description": "Audit and optimize cold email angles for better reply rates"},
        {"title": "Create TikTok account", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 10),
         "description": "Set up TikTok business account for Grindlab"},
        {"title": "Create Rumble account", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 10),
         "description": "Set up Rumble channel for content cross-posting"},
        {"title": "Activate subscribers for testimonials", "priority": TaskPriority.launch_critical,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 12),
         "description": "Reach out to engaged subscribers for early testimonials"},

        # High Priority
        {"title": "Set up Stripe payment integration", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "clint", "due_date": date(2026, 3, 18),
         "description": "Integrate Stripe for subscription payments"},
        {"title": "Build landing page v2", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 15),
         "description": "Redesign landing page with new messaging and social proof"},
        {"title": "Reddit content calendar", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 14),
         "description": "Plan 30 days of Reddit posts across poker subreddits"},
        {"title": "Film 5 Study Science Drop videos", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 20),
         "description": "Record batch of short-form educational content"},
        {"title": "Set up Meta Pixel on all pages", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "clint", "due_date": date(2026, 3, 12),
         "description": "Install Meta Pixel via GTM on grindlab.ai"},
        {"title": "Configure GA4 conversion events", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 12),
         "description": "Set up trial_start, quiz_complete, purchase events in GA4"},
        {"title": "Write nurture email #4-7", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 16),
         "description": "Complete the nurture drip sequence emails 4 through 7"},
        {"title": "Design affiliate commission structure", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 22),
         "description": "Define tiers, rates, and payout structure for affiliates"},
        {"title": "SparkLoop reward tier setup", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 14),
         "description": "Configure SparkLoop referral reward tiers"},
        {"title": "Identify top 20 poker influencers", "priority": TaskPriority.high,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 15),
         "description": "Research and list top 20 poker content creators for outreach"},

        # Medium Priority
        {"title": "Set up Hotjar on key pages", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 18),
         "description": "Install Hotjar on landing, pricing, and quiz pages"},
        {"title": "Create Instagram content templates", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 20),
         "description": "Design reusable templates for IG posts and stories"},
        {"title": "Build Buffer posting schedule", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 12),
         "description": "Set up optimal posting times in Buffer for X and IG"},
        {"title": "Write 3 blog posts for SEO", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 25),
         "description": "Create pillar content targeting poker study keywords"},
        {"title": "Create exit survey for cancellations", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 28),
         "description": "Build exit survey to capture cancellation reasons"},
        {"title": "Set up automated weekly metrics report", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 18),
         "description": "Automate weekly summary of key metrics via n8n"},
        {"title": "Research Reddit ad targeting options", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 20),
         "description": "Investigate Reddit ads for poker subreddits"},
        {"title": "Draft ambassador program terms", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 25),
         "description": "Write terms and expectations for brand ambassadors"},
        {"title": "Set up Rewardful for affiliates", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 28),
         "description": "Configure Rewardful platform for affiliate tracking"},
        {"title": "Create lead magnet PDF", "priority": TaskPriority.medium,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 15),
         "description": "Design downloadable PDF for email list growth"},

        # Low Priority
        {"title": "Competitive pricing analysis update", "priority": TaskPriority.low,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 30),
         "description": "Update competitor pricing comparison"},
        {"title": "Write YouTube channel description", "priority": TaskPriority.low,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 15),
         "description": "Optimize YouTube channel page with keywords and links"},
        {"title": "Create social proof widget", "priority": TaskPriority.low,
         "status": TaskStatus.backlog, "assigned_to": "clint", "due_date": date(2026, 3, 25),
         "description": "Build a live notification widget showing recent signups"},
        {"title": "Set up Discord server", "priority": TaskPriority.low,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 4, 5),
         "description": "Create Discord community server for Grindlab users"},
        {"title": "Create FAQ page", "priority": TaskPriority.low,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 3, 28),
         "description": "Build FAQ page addressing common questions"},

        # Cleanup
        {"title": "Audit all tracking pixels", "priority": TaskPriority.cleanup,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 4, 5),
         "description": "Verify all tracking pixels fire correctly on all pages"},
        {"title": "Clean up unused ConvertKit tags", "priority": TaskPriority.cleanup,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 4, 5),
         "description": "Remove or consolidate unused subscriber tags"},
        {"title": "Document all n8n workflows", "priority": TaskPriority.cleanup,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 4, 10),
         "description": "Create documentation for all automation workflows"},
        {"title": "Review and update cold email copy", "priority": TaskPriority.cleanup,
         "status": TaskStatus.backlog, "assigned_to": "phil", "due_date": date(2026, 4, 5),
         "description": "Refresh cold email templates based on performance data"},
        {"title": "Optimize Leak Finder quiz load time", "priority": TaskPriority.cleanup,
         "status": TaskStatus.backlog, "assigned_to": "clint", "due_date": date(2026, 4, 10),
         "description": "Improve page speed for the Leak Finder quiz"},

        # Recurring
        {"title": "Daily Reddit engagement", "priority": TaskPriority.medium,
         "status": TaskStatus.recurring, "assigned_to": "phil",
         "recurring_schedule": "0 9 * * *", "recurring_frequency": "daily",
         "recurring_next_due": date(2026, 3, 6),
         "description": "Post and engage in poker subreddits daily"},
        {"title": "Weekly content batch", "priority": TaskPriority.high,
         "status": TaskStatus.recurring, "assigned_to": "phil",
         "recurring_schedule": "0 10 * * 1", "recurring_frequency": "weekly",
         "recurring_next_due": date(2026, 3, 9),
         "description": "Film/write weekly batch of content pieces"},
        {"title": "Weekly metrics review", "priority": TaskPriority.high,
         "status": TaskStatus.recurring, "assigned_to": "phil",
         "recurring_schedule": "0 9 * * 0", "recurring_frequency": "weekly",
         "recurring_next_due": date(2026, 3, 8),
         "description": "Review all channel metrics and update MCC"},
        {"title": "Bi-weekly cold email audit", "priority": TaskPriority.medium,
         "status": TaskStatus.recurring, "assigned_to": "phil",
         "recurring_schedule": "0 10 1,15 * *", "recurring_frequency": "biweekly",
         "recurring_next_due": date(2026, 3, 15),
         "description": "Audit cold email performance and rotate underperforming angles"},
        {"title": "Monthly competitor check", "priority": TaskPriority.medium,
         "status": TaskStatus.recurring, "assigned_to": "phil",
         "recurring_schedule": "0 10 1 * *", "recurring_frequency": "monthly",
         "recurring_next_due": date(2026, 4, 1),
         "description": "Check competitor sites for pricing/feature changes"},
    ]

    for td in tasks_data:
        db.add(Task(project_id=pid, **td))

    # --- Automations (10+) ---
    automations_data = [
        {"name": "Reddit Daily Brief", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": "0 7 * * *",
         "expected_run_interval_hours": 24, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.log_check, "owner": "scotty",
         "hosting": HostingLocation.mac_mini,
         "notes": "Scrapes poker subreddits, generates daily brief"},
        {"name": "Milestone Alerts", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": "0 */4 * * *",
         "expected_run_interval_hours": 4, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.log_check, "owner": "scotty",
         "hosting": HostingLocation.mac_mini,
         "notes": "Checks subscriber milestones and triggers alerts"},
        {"name": "Weekly Metrics Rollup", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": "0 8 * * 0",
         "expected_run_interval_hours": 168, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.log_check, "owner": "scotty",
         "hosting": HostingLocation.mac_mini,
         "notes": "Aggregates weekly metrics from all channels"},
        {"name": "Pipeline Health Check", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": None,
         "expected_run_interval_hours": None, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.manual_confirm, "owner": "scotty",
         "hosting": HostingLocation.mac_mini,
         "notes": "On-demand pipeline health verification"},
        {"name": "Kit Nurture v3", "automation_type": AutomationType.email_sequence,
         "platform": "ConvertKit", "schedule": "Triggered on signup",
         "expected_run_interval_hours": None, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.api_poll, "owner": "phil",
         "hosting": HostingLocation.cloud,
         "notes": "7-email nurture drip triggered by list signup"},
        {"name": "n8n Leak Finder Pipeline", "automation_type": AutomationType.webhook_pipeline,
         "platform": "Railway n8n", "schedule": "Triggered on quiz completion",
         "expected_run_interval_hours": None, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.webhook_heartbeat, "owner": "scotty",
         "hosting": HostingLocation.cloud,
         "notes": "Processes quiz results, sends results email, adds to Kit"},
        {"name": "n8n Instantly-Reply Pipeline", "automation_type": AutomationType.webhook_pipeline,
         "platform": "Railway n8n", "schedule": "Triggered on positive reply",
         "expected_run_interval_hours": None, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.webhook_heartbeat, "owner": "scotty",
         "hosting": HostingLocation.cloud,
         "notes": "Routes positive cold email replies for follow-up"},
        {"name": "Buffer Scheduled Posts", "automation_type": AutomationType.scheduled_post,
         "platform": "Buffer", "schedule": "Per Buffer schedule",
         "expected_run_interval_hours": 24, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.api_poll, "owner": "phil",
         "hosting": HostingLocation.cloud,
         "notes": "Auto-publishes queued social posts"},
        {"name": "Instantly Warmup/Send", "automation_type": AutomationType.cron_job,
         "platform": "Instantly", "schedule": "Continuous",
         "expected_run_interval_hours": 24, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.api_poll, "owner": "phil",
         "hosting": HostingLocation.cloud,
         "notes": "Continuous email warmup and cold send sequences"},
        {"name": "SparkLoop Referral Tracking", "automation_type": AutomationType.referral_program,
         "platform": "SparkLoop", "schedule": "Continuous",
         "expected_run_interval_hours": 24, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.manual_confirm, "owner": "phil",
         "hosting": HostingLocation.cloud,
         "notes": "Tracks newsletter referrals and applies reward tiers"},
        {"name": "MCC Daily Backup", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": "0 3 * * *",
         "expected_run_interval_hours": 26, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.log_check, "owner": "scotty",
         "hosting": HostingLocation.mac_mini,
         "script_path": "~/marketing-command-center/scripts/daily_backup.sh",
         "notes": "Auto-commits code to GitHub, backs up database, prunes old backups (14-day retention)"},
        {"name": "Mac Mini Heartbeat", "automation_type": AutomationType.cron_job,
         "platform": "Mac Mini cron", "schedule": "Every 30 minutes",
         "expected_run_interval_hours": 1, "health": AutomationHealth.running,
         "health_check_method": HealthCheckMethod.log_check, "owner": "System",
         "hosting": HostingLocation.mac_mini,
         "script_path": "scripts/heartbeat_ping.sh",
         "notes": "Dead man switch — pings Healthchecks.io every 30min. If this stops, external alert fires."},
    ]

    for ad in automations_data:
        db.add(Automation(project_id=pid, **ad))

    # --- Email Sequences (6) ---
    sequences_data = [
        {"name": "Nurture Drip v3", "sequence_type": SequenceType.nurture_drip,
         "platform": "ConvertKit", "email_count": 7, "status": SequenceStatus.live,
         "trigger": "Signup to email list", "open_rate": 42.5, "click_rate": 8.2,
         "subscribers_active": 112, "notes": "Main nurture sequence for new subscribers"},
        {"name": "Leak Finder Results", "sequence_type": SequenceType.triggered,
         "platform": "Resend via n8n", "email_count": 1, "status": SequenceStatus.live,
         "trigger": "Leak Finder quiz completion",
         "notes": "Sends personalized results after quiz completion"},
        {"name": "Lead Magnet Delivery", "sequence_type": SequenceType.triggered,
         "platform": "ConvertKit", "email_count": 1, "status": SequenceStatus.live,
         "trigger": "Lead magnet download request",
         "notes": "Delivers PDF lead magnet and adds to nurture"},
        {"name": "Launch Countdown", "sequence_type": SequenceType.nurture_drip,
         "platform": "ConvertKit", "email_count": 8, "status": SequenceStatus.needs_build,
         "trigger": "Manual trigger at T-14 days",
         "notes": "6-8 email sequence building excitement for launch"},
        {"name": "Trial Expiration", "sequence_type": SequenceType.retention,
         "platform": "ConvertKit", "email_count": 3, "status": SequenceStatus.needs_build,
         "trigger": "Trial expiration date approaching",
         "notes": "3-email sequence to convert expiring trials"},
        {"name": "Onboarding Activation", "sequence_type": SequenceType.onboarding,
         "platform": "ConvertKit", "email_count": 1, "status": SequenceStatus.needs_build,
         "trigger": "Free trial signup",
         "notes": "Welcome email with first steps and quick wins"},
    ]

    for sd in sequences_data:
        db.add(EmailSequence(project_id=pid, **sd))

    # --- Competitors (4) ---
    competitors_data = [
        {"name": "Upswing Poker", "website": "https://upswingpoker.com",
         "pricing_summary": "$99-199 one-time courses, $999 lab membership",
         "positioning_summary": "Premium poker education from top pros",
         "strengths": "Strong brand recognition, elite coaches (Doug Polk), comprehensive course library, large YouTube following",
         "weaknesses": "High price point, course-based (not adaptive), no personalized study plans, outdated UI",
         "key_channels": ["YouTube", "Instagram", "Email", "Google Ads"]},
        {"name": "PokerCoaching.com", "website": "https://pokercoaching.com",
         "pricing_summary": "$30/mo subscription",
         "positioning_summary": "Jonathan Little's coaching platform with courses and quizzes",
         "strengths": "Affordable monthly price, Jonathan Little's name recognition, regular content updates, quiz features",
         "weaknesses": "Generic study approach, no AI personalization, cluttered interface, no session tracking",
         "key_channels": ["YouTube", "Email", "Instagram", "Facebook Ads"]},
        {"name": "GTO Wizard", "website": "https://gtowizard.com",
         "pricing_summary": "Varies by tier, solver-based pricing",
         "positioning_summary": "GTO solver and training tool for serious players",
         "strengths": "Best solver technology, beautiful UI, strong brand in GTO community, practice mode",
         "weaknesses": "Intimidating for beginners, pure GTO focus (no exploitative), expensive at higher tiers, no study plan",
         "key_channels": ["Twitter/X", "YouTube", "Discord", "Reddit"]},
        {"name": "Run It Once", "website": "https://www.runitonce.com",
         "pricing_summary": "Varies, subscription model",
         "positioning_summary": "Phil Galfond's poker training site with elite content",
         "strengths": "Phil Galfond brand, high-quality video content, strong community, poker room integration",
         "weaknesses": "Less focused on study methodology, traditional video format, no AI features, dated platform",
         "key_channels": ["Twitch", "YouTube", "Twitter/X", "Email"]},
    ]

    for cd in competitors_data:
        db.add(Competitor(project_id=pid, **cd))

    # --- Ad Campaigns (3) ---
    paid_channel = channel_objs["Paid Ads"]
    ads_data = [
        {"platform": AdPlatform.meta, "campaign_name": "Leak Finder Quiz - Cold Traffic",
         "status": AdStatus.active, "objective": AdObjective.conversions,
         "daily_budget": 25, "total_budget": 750, "spend_to_date": 142.50,
         "impressions": 18500, "clicks": 370, "ctr": 2.0, "conversions": 28, "cpl": 5.09,
         "roas": 0, "cpm": 7.70, "signal": AdSignal.scale,
         "signal_reason": "CPL $5.09 below $10 target, CTR 2.0% strong",
         "creative_notes": "Carousel ad: '5 Leaks Costing You $$$' — best performer",
         "start_date": date(2026, 2, 15)},
        {"platform": AdPlatform.reddit, "campaign_name": "r/poker Awareness",
         "status": AdStatus.active, "objective": AdObjective.awareness,
         "daily_budget": 15, "total_budget": 450, "spend_to_date": 89.25,
         "impressions": 32000, "clicks": 192, "ctr": 0.6, "conversions": 5, "cpl": 17.85,
         "roas": 0, "cpm": 2.79, "signal": AdSignal.optimize,
         "signal_reason": "CPL $17.85 above target, low CTR — test new copy",
         "creative_notes": "Text ad targeting r/poker subscribers",
         "start_date": date(2026, 2, 20)},
        {"platform": AdPlatform.meta, "campaign_name": "Retarget Quiz Abandoners",
         "status": AdStatus.paused, "objective": AdObjective.retargeting,
         "daily_budget": 10, "total_budget": 300, "spend_to_date": 45.00,
         "impressions": 4200, "clicks": 84, "ctr": 2.0, "conversions": 3, "cpl": 15.00,
         "roas": 0, "cpm": 10.71, "signal": AdSignal.hold,
         "signal_reason": "Small audience — wait for more quiz traffic before scaling",
         "creative_notes": "Single image: 'Finish Your Leak Finder Report'",
         "start_date": date(2026, 2, 25)},
    ]

    for ad in ads_data:
        db.add(AdCampaign(project_id=pid, channel_id=paid_channel.id, **ad))

    # --- Outreach Contacts (10) ---
    contacts_data = [
        {"name": "Lexy Gavin-Mather", "platform": "YouTube", "audience_size": 289000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Large poker YouTube channel, good fit for Grindlab demo"},
        {"name": "hungry horse poker", "platform": "YouTube", "audience_size": 184000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Growing poker vlog channel, relatable content style"},
        {"name": "Brad Owen", "platform": "YouTube", "audience_size": 900000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Top poker vlogger, massive reach"},
        {"name": "Andrew Neeme", "platform": "YouTube", "audience_size": 400000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Popular poker vlogger, quality production"},
        {"name": "Mariano", "platform": "YouTube", "audience_size": 250000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Poker content creator with engaged audience"},
        {"name": "Jaman Burton", "platform": "YouTube", "audience_size": 150000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Poker strategy and vlog content"},
        {"name": "Wolfgang Poker", "platform": "YouTube", "audience_size": 300000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "European poker content, large following"},
        {"name": "Ethan Yau (Rampage)", "platform": "YouTube", "audience_size": 500000,
         "contact_type": ContactType.influencer, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Viral poker content, huge subscriber base"},
        {"name": "Matt Berkey", "platform": "YouTube", "audience_size": 100000,
         "contact_type": ContactType.coach, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Respected poker coach, Solve For Why founder"},
        {"name": "Bart Hanson", "platform": "YouTube", "audience_size": 120000,
         "contact_type": ContactType.coach, "status": ContactStatus.identified,
         "outreach_stage": 1, "notes": "Crush Live Poker host, experienced coach"},
    ]

    for cd in contacts_data:
        db.add(OutreachContact(project_id=pid, **cd))

    # --- Onboarding Milestones (8) ---
    milestones_data = [
        {"name": "Complete Leak Finder quiz", "description": "User completes the initial skill assessment quiz",
         "target_days_from_start": 1, "display_order": 1},
        {"name": "Log first session", "description": "User logs their first poker session in the tracker",
         "target_days_from_start": 2, "display_order": 2},
        {"name": "Record first hand", "description": "User records their first notable hand for review",
         "target_days_from_start": 3, "display_order": 3},
        {"name": "Complete first study plan", "description": "User completes their first AI-generated study plan",
         "target_days_from_start": 5, "display_order": 4},
        {"name": "Return for second session", "description": "User comes back for a second study session",
         "target_days_from_start": 7, "display_order": 5},
        {"name": "Run a drill", "description": "User completes at least one practice drill",
         "target_days_from_start": 14, "display_order": 6},
        {"name": "Active in Week 3", "description": "User logs in during their third week",
         "target_days_from_start": 21, "display_order": 7},
        {"name": "Trial Day 25+ conversion window", "description": "User reaches conversion decision point",
         "target_days_from_start": 25, "display_order": 8},
    ]

    for md in milestones_data:
        db.add(OnboardingMilestone(project_id=pid, **md))

    # --- Initial Metrics ---
    email_channel = channel_objs["Email Nurture (Kit)"]
    cold_channel = channel_objs["Cold Email (Instantly)"]

    db.add(Metric(channel_id=email_channel.id, metric_name="subscribers",
                  metric_value=112, unit="count", source=MetricSource.manual))
    db.add(Metric(channel_id=cold_channel.id, metric_name="total_sends",
                  metric_value=250, unit="count", source=MetricSource.manual))
    db.add(Metric(channel_id=cold_channel.id, metric_name="replies",
                  metric_value=0, unit="count", source=MetricSource.manual))

    # --- Autonomous Tools (Scotty) ---
    db.add(AutonomousTool(
        project_id=pid,
        name="Scotty",
        tool_type=AutonomousToolType.bot,
        platform="Mac Mini cron",
        workspace_path="~/clawd/projects/scotty",
        expected_heartbeat_hours=24,
        owner="scotty",
        notes="Autonomous marketing bot — runs reddit_daily_brief, milestone_alerts, weekly_metrics_rollup, pipeline_health_check",
        api_key=uuid.uuid4().hex,
        health=AutonomousToolHealth.online,
    ))

    # --- Brand Colors ---
    brand_colors = [
        {"name": "Grindlab Green", "hex_code": "#00C853", "usage_notes": "Primary brand color, CTAs, success states", "sort_order": 0},
        {"name": "Navy", "hex_code": "#003366", "usage_notes": "Headings, dark backgrounds, authority", "sort_order": 1},
        {"name": "Dark Background", "hex_code": "#0B0B1A", "usage_notes": "Page backgrounds, dark mode base", "sort_order": 2},
        {"name": "Card Surface", "hex_code": "#16162E", "usage_notes": "Card backgrounds, elevated surfaces", "sort_order": 3},
        {"name": "Accent Cyan", "hex_code": "#06B6D4", "usage_notes": "Links, interactive elements, highlights", "sort_order": 4},
        {"name": "Warning Gold", "hex_code": "#F59E0B", "usage_notes": "Warnings, attention-needed states", "sort_order": 5},
        {"name": "Critical Red", "hex_code": "#EF4444", "usage_notes": "Errors, destructive actions, overdue", "sort_order": 6},
        {"name": "Text Primary", "hex_code": "#E8E8F0", "usage_notes": "Primary text on dark backgrounds", "sort_order": 7},
        {"name": "Text Muted", "hex_code": "#6B6B8A", "usage_notes": "Secondary text, labels, captions", "sort_order": 8},
    ]
    for bc in brand_colors:
        db.add(BrandColor(project_id=pid, **bc))

    # --- Brand Fonts ---
    brand_fonts = [
        {"name": "Inter", "usage": "Primary — headings, body, UI", "font_url": "https://fonts.google.com/specimen/Inter", "sort_order": 0},
        {"name": "JetBrains Mono", "usage": "Code, data, metrics display", "font_url": "https://fonts.google.com/specimen/JetBrains+Mono", "sort_order": 1},
        {"name": "Impact", "usage": "Thumbnail headlines, YouTube titles", "sort_order": 2},
    ]
    for bf in brand_fonts:
        db.add(BrandFont(project_id=pid, **bf))

    # --- Platform Profiles ---
    profiles = [
        {"platform": "YouTube", "handle": "@GrindlabAI", "profile_url": "https://youtube.com/@GrindlabAI",
         "bio_text": "AI-powered poker study tools. Stop guessing, start grinding. Free Leak Finder quiz at grindlab.ai",
         "link": "https://grindlab.ai", "sort_order": 0},
        {"platform": "Instagram", "handle": "@grindlabpoker", "profile_url": "https://instagram.com/grindlabpoker",
         "bio_text": "Your poker game has leaks. We find them. AI-powered study tools for serious grinders. Free Leak Finder below.",
         "link": "https://grindlab.ai/quiz", "sort_order": 1},
        {"platform": "TikTok", "handle": "@grindlabpoker", "profile_url": "https://tiktok.com/@grindlabpoker",
         "bio_text": "Poker study tips + AI tools. Find your leaks free at grindlab.ai",
         "link": "https://grindlab.ai/quiz", "sort_order": 2},
        {"platform": "X/Twitter", "handle": "@Grindlab_AI", "profile_url": "https://x.com/Grindlab_AI",
         "bio_text": "AI-powered poker study platform. Leak Finder quiz, personalized study plans, session tracking. Built by grinders, for grinders.",
         "link": "https://grindlab.ai", "sort_order": 3},
        {"platform": "Reddit", "handle": "u/grindlab", "profile_url": "https://reddit.com/u/grindlab",
         "bio_text": "Building Grindlab — AI poker study tools. Here to help the community improve.",
         "link": "https://grindlab.ai", "sort_order": 4},
    ]
    for pp in profiles:
        db.add(PlatformProfile(project_id=pid, **pp))

    # --- Brand Guidelines ---
    db.add(BrandGuidelines(
        project_id=pid,
        voice_rules="Tool language, not coach language. Say 'the Leak Finder identified' not 'we noticed'. "
                    "Grindlab is the tool, Phil is the human behind it. Never position as a coaching service — "
                    "we're a study platform. Speak to grinders (serious recreational players who want to improve), "
                    "not beginners or pros. Be direct, data-driven, slightly irreverent.",
        banned_words="Guru, masterclass, crush the competition, easy money, get rich, guaranteed, secrets, "
                     "hack (as noun), unlock your potential, level up (overused), game-changer, revolutionary",
        tone_description="Confident but not arrogant. Technical but accessible. Like a sharp friend at the poker "
                        "table who knows their stuff and doesn't sugarcoat it. We respect the grind.",
        content_mix="60% Education (study tips, hand analysis, strategy concepts)\n"
                   "30% Entertainment (poker culture, relatable moments, room reviews)\n"
                   "10% Promotion (product features, CTAs, testimonials)",
        notes="Always lead with value. Every piece of content should teach something or entertain. "
              "Promotion is earned by providing value first. The Leak Finder quiz is the primary conversion "
              "tool — reference it naturally, never force it.",
    ))

    # --- Grindlab Launch Template ---
    tmpl = LaunchTemplate(
        name="Grindlab Launch",
        description="Complete SaaS product launch template based on the Grindlab poker study platform launch. "
                   "Covers pre-launch setup, content creation, email sequences, ad campaigns, and post-launch monitoring.",
        created_from_project_id=pid,
    )
    db.add(tmpl)
    db.flush()

    launch_date = date(2026, 4, 1)
    template_tasks = [
        {"title": "Website strategy decision", "relative_day": -22, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Decide on website architecture and tech approach"},
        {"title": "Create TikTok account", "relative_day": -22, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Set up TikTok business account"},
        {"title": "Create Rumble account", "relative_day": -22, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Set up Rumble channel for content cross-posting"},
        {"title": "Cold email angle audit", "relative_day": -20, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Audit and optimize cold email angles"},
        {"title": "Activate subscribers for testimonials", "relative_day": -20, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Reach out to engaged subscribers for early testimonials"},
        {"title": "Set up Meta Pixel on all pages", "relative_day": -20, "priority": TaskPriority.high,
         "assigned_role": "developer", "description": "Install tracking pixel via GTM"},
        {"title": "Configure analytics conversion events", "relative_day": -20, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Set up trial_start, quiz_complete, purchase events"},
        {"title": "Build landing page v2", "relative_day": -17, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Redesign landing page with new messaging and social proof"},
        {"title": "Create lead magnet PDF", "relative_day": -17, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Design downloadable PDF for email list growth"},
        {"title": "Content calendar (30 days)", "relative_day": -18, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Plan 30 days of social posts across platforms"},
        {"title": "Referral program setup", "relative_day": -18, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Configure referral reward tiers"},
        {"title": "Identify top 20 influencers", "relative_day": -17, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Research and list top content creators for outreach"},
        {"title": "Write nurture email sequence", "relative_day": -16, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Complete the nurture drip sequence"},
        {"title": "Set up payment integration", "relative_day": -14, "priority": TaskPriority.high,
         "assigned_role": "developer", "description": "Integrate payment processor for subscriptions"},
        {"title": "Purchase page copy", "relative_day": -12, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Write copy for the purchase/pricing page"},
        {"title": "Film content batch", "relative_day": -12, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Record batch of short-form educational content"},
        {"title": "Launch countdown email sequence", "relative_day": -9, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Build countdown sequence in email platform"},
        {"title": "Cancellation/pause flow spec", "relative_day": -7, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Define cancellation and pause flow with exit survey"},
        {"title": "Trial expiration flow", "relative_day": -4, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "3-email sequence triggered when free trial expires"},
        {"title": "Onboarding activation email", "relative_day": -4, "priority": TaskPriority.launch_critical,
         "assigned_role": "founder", "description": "Welcome email with first steps after signup"},
        {"title": "Design affiliate commission structure", "relative_day": -10, "priority": TaskPriority.high,
         "assigned_role": "founder", "description": "Define tiers, rates, and payout structure"},
        {"title": "Set up heatmaps on key pages", "relative_day": -14, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Install heatmap tool on landing, pricing, and quiz pages"},
        {"title": "Social posting schedule", "relative_day": -20, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Set up optimal posting times in scheduler"},
        {"title": "Write blog posts for SEO", "relative_day": -7, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Create pillar content targeting key search terms"},
        {"title": "Research paid ad targeting", "relative_day": -12, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Investigate ad platform targeting options"},
        {"title": "Set up affiliate platform", "relative_day": -4, "priority": TaskPriority.medium,
         "assigned_role": "founder", "description": "Configure affiliate tracking platform"},
        {"title": "Competitive pricing analysis", "relative_day": -2, "priority": TaskPriority.low,
         "assigned_role": "founder", "description": "Update competitor pricing comparison"},
        {"title": "Create FAQ page", "relative_day": -4, "priority": TaskPriority.low,
         "assigned_role": "founder", "description": "Build FAQ page addressing common questions"},
        {"title": "Audit all tracking pixels", "relative_day": 5, "priority": TaskPriority.cleanup,
         "assigned_role": "founder", "description": "Verify all tracking pixels fire correctly"},
        {"title": "Document all workflows", "relative_day": 10, "priority": TaskPriority.cleanup,
         "assigned_role": "founder", "description": "Create documentation for all automation workflows"},
    ]

    for tt in template_tasks:
        db.add(TemplateTask(template_id=tmpl.id, **tt))

    db.commit()
