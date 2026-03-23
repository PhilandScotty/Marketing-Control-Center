#!/usr/bin/env python3
"""Load Grindlab Growth Engine tasks into MCC database.
Checks for duplicates, updates existing tasks, creates new ones.
Creates new channels (categories) as needed.
"""

import sqlite3
from datetime import datetime

DB_PATH = "data/mcc.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

PROJECT_ID = 1  # Grindlab

# Track results
created = []
updated = []
skipped = []
new_channels = []

# ─── STEP 1: Create missing channels ───────────────────────────────
def get_or_create_channel(name, channel_type="owned"):
    cur.execute("SELECT id FROM channels WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    now = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO channels (project_id, name, channel_type, status, automation_level, owner, health, created_at, updated_at)
           VALUES (?, ?, ?, 'active', 'manual', 'phil', 'good', ?, ?)""",
        (PROJECT_ID, name, channel_type, now, now),
    )
    conn.commit()
    cid = cur.lastrowid
    new_channels.append(name)
    print(f"  [NEW CHANNEL] #{cid}: {name}")
    return cid

# Create/get all needed channels
ch_website_seo = get_or_create_channel("Website / SEO")
ch_content_blog = get_or_create_channel("Content / Blog")
ch_outreach = get_or_create_channel("Outreach")
ch_automation = get_or_create_channel("Automation / Scotty")
ch_technical = get_or_create_channel("Technical (Clint)")
ch_lead_magnets = get_or_create_channel("Lead Magnets")
ch_leak_finder = 3   # existing
ch_influencer = 9    # existing
ch_forum = 15        # existing
ch_youtube = 7       # existing
ch_sparkloop = 8     # existing
ch_paid_ads = 12     # existing

# ─── STEP 2: Helper to create or update tasks ──────────────────────
def upsert_task(title, description, priority, assigned_to, due_date, channel_id,
                estimated_hours=None, status="backlog", blocker_note="",
                existing_id=None, recurring_frequency=None):
    """Create or update a task. If existing_id is given, update that task."""
    now = datetime.utcnow().isoformat()

    # Append blocker note to description if present
    full_desc = description
    if blocker_note:
        full_desc += f"\n\nBLOCKER: {blocker_note}"

    if existing_id:
        cur.execute(
            """UPDATE tasks SET
                title = ?, description = ?, priority = ?, assigned_to = ?,
                due_date = ?, channel_id = ?, estimated_hours = ?,
                status = CASE WHEN status IN ('done', 'archived') THEN status ELSE ? END,
                recurring_frequency = COALESCE(?, recurring_frequency),
                updated_at = ?
            WHERE id = ?""",
            (title, full_desc, priority, assigned_to, due_date, channel_id,
             estimated_hours, status, recurring_frequency, now, existing_id),
        )
        updated.append((existing_id, title))
        print(f"  [UPDATED] #{existing_id}: {title}")
        return existing_id
    else:
        cur.execute(
            """INSERT INTO tasks (project_id, channel_id, title, description, status, priority,
                assigned_to, due_date, estimated_hours, blocked_by, blocks,
                recurring_frequency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?, ?)""",
            (PROJECT_ID, channel_id, title, full_desc, status, priority,
             assigned_to, due_date, estimated_hours, recurring_frequency, now, now),
        )
        tid = cur.lastrowid
        created.append((tid, title))
        print(f"  [CREATED] #{tid}: {title}")
        return tid


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: TECHNICAL SEO FIXES (March 9-15)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 1: TECHNICAL SEO FIXES ──")

upsert_task(
    title="Add sitemap.xml to grindlab.ai",
    description="grindlab.ai/sitemap.xml returns 404. Install next-sitemap in the Next.js Pages Router project. Auto-generate sitemap on each Vercel deploy. Must include all current routes: /, /leakfinder, /contact, /privacy-policy, /terms-of-service, /cookie-policy. Must auto-include /blog/* and /rooms/* routes when those are added later.",
    priority="launch_critical",
    assigned_to="clint",
    due_date="2026-03-14",
    channel_id=ch_technical,
    estimated_hours=1.0,
    status="this_week",
)

upsert_task(
    title="Add Sitemap reference to robots.txt",
    description="Current robots.txt is Cloudflare-managed. Add line: Sitemap: https://grindlab.ai/sitemap.xml. Check if this needs to be done in Cloudflare dashboard or if it can be added to the Next.js public/ directory. The Cloudflare-managed robots.txt currently allows Googlebot (search=yes) which is correct — don't change that.",
    priority="launch_critical",
    assigned_to="clint",
    due_date="2026-03-14",
    channel_id=ch_technical,
    estimated_hours=0.25,
    status="this_week",
    blocker_note="Need to determine if robots.txt is editable via repo or only via Cloudflare.",
)

# Task 47 exists: "Add OG meta tags to homepage and /leakfinder" — different from canonical tags
upsert_task(
    title="Add canonical tags to all pages",
    description="Homepage has canonical tag (good). /leakfinder is MISSING canonical tag. Add <link rel=\"canonical\"> to every page. Use next/head or _document.js. Canonical should be the full URL including https://www.grindlab.ai/[path].",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-14",
    channel_id=ch_technical,
    estimated_hours=0.5,
    status="this_week",
)

# Task 47 covers OG tags. Structured data (schema markup) is different — create new.
upsert_task(
    title="Add structured data (schema markup) to homepage and leakfinder",
    description="Add Organization schema to homepage, FAQPage schema to the FAQ section (7 questions already on page — perfect for FAQ rich snippets), WebSite schema with SearchAction. Add Quiz schema to /leakfinder. Claude will draft the JSON-LD. Clint adds it via <script type=\"application/ld+json\"> in the page head.",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-21",
    channel_id=ch_technical,
    estimated_hours=0.75,
    blocker_note="Claude needs to draft the JSON-LD first (do in project chat).",
)

# Task 48 exists: "Update page title from GrindLab AI to keyword-targeted title" — UPDATE it
upsert_task(
    title="Optimize homepage title tag for SEO",
    description="Current title: \"Grindlab — The Study Caddy for Poker Players\". Nobody searches for \"study caddy\". Change to: \"Grindlab | Poker Study System — Learn, Retain, Recall Under Pressure\" or \"Grindlab | The Poker Study App — Track Leaks, Build Study Plans, Train Under Pressure\". Target keywords: \"poker study system\", \"poker study app\". Keep brand name first for recognition.",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-14",
    channel_id=ch_website_seo,
    estimated_hours=0.1,
    status="this_week",
    existing_id=48,
    blocker_note="Phil must approve final title.",
)

upsert_task(
    title="Add secondary CTA to homepage (Leak Finder quiz)",
    description="Currently the only CTA on the homepage is \"Join the Waitlist.\" Add a secondary CTA below the first form: \"Not ready to join? Take the free Leak Finder quiz — find your top 3 leaks in 3 minutes.\" This catches visitors at lower intent who won't give their email for a waitlist but will engage with a free tool. Also add a Leak Finder callout in the \"Your Study Caddy\" feature cards section.",
    priority="medium",
    assigned_to="clint",
    due_date="2026-03-21",
    channel_id=ch_website_seo,
    estimated_hours=0.5,
)

# Task 33 exists: "Create social proof widget" — UPDATE with richer description
upsert_task(
    title="Add social proof element to homepage",
    description="Add \"Join [X] poker players on the waitlist\" counter near the signup form. Pull count from Kit API or hardcode and update weekly. Post-launch: add quiz completion counter on /leakfinder (\"X players have found their leaks\"). Week 4+: add real user quotes from early trial users.",
    priority="medium",
    assigned_to="clint",
    due_date="2026-03-28",
    channel_id=ch_website_seo,
    estimated_hours=1.0,
    existing_id=33,
    blocker_note="Need Kit subscriber count API call (already in MCC infra).",
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: OPTION B COPY REFRESH (March 10-21)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 2: OPTION B COPY REFRESH ──")

upsert_task(
    title="Write Option B homepage copy refresh",
    description="Rewrite hero headline, sub-headline, CTA copy, and feature section copy for conversion (trial signup, not waitlist). Use copy from GRINDLAB-WEBSITE-STRATEGY.md Section 3 as starting point. Must target \"poker study\" keywords. Remove all \"Launching April 1\" and \"waitlist\" language — replace with trial signup language that goes live March 31. Draft already exists in website strategy doc — finalize and get Phil approval.",
    priority="high",
    assigned_to="claude",
    due_date="2026-03-15",
    channel_id=ch_website_seo,
    estimated_hours=0.75,
    status="this_week",
    blocker_note="Phil must review and approve.",
)

upsert_task(
    title="Clint implements Option B copy refresh",
    description="Find-and-replace style implementation. Phil/Claude provide exact copy. Update: hero headline, sub-headline, CTA button text (waitlist → trial), feature section copy, pricing section copy (add trial language), footer copy. No layout changes. No URL changes. No new pages.",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-21",
    channel_id=ch_technical,
    estimated_hours=5.0,
    blocker_note="Copy must be approved by Phil first.",
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 3: BLOG INFRASTRUCTURE (March 16-31)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 3: BLOG INFRASTRUCTURE ──")

upsert_task(
    title="Clint adds /blog route to Next.js",
    description="Add /blog/[slug] route to Next.js Pages Router. Blog posts as MDX files in the repo (lowest friction for Phil/Claude to add content via PR). Each post needs: URL slug from filename, frontmatter for title/description/date/author/keywords/CTA type, auto-generated meta tags from frontmatter, breadcrumb nav, related posts component (can be simple — 2-3 links), CTA component (configurable: quiz CTA, email CTA, or trial CTA), Article schema (JSON-LD) auto-generated from frontmatter. Posts auto-added to sitemap.",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-28",
    channel_id=ch_technical,
    estimated_hours=10.0,
    blocker_note="Sitemap must be working first.",
)

# Task 24 exists: "Write 3 blog posts for SEO" — UPDATE to 4 posts with full details
upsert_task(
    title="Write first 4 blog posts",
    description="Posts 1-4 from the blog calendar: (1) \"How to Study Poker: The Complete Guide\" — pillar article, 2000+ words, targets \"how to study poker\". (2) \"GTO Wizard vs Grindlab: Which Is Right for You?\" — alternative page, 1000 words, targets \"GTO Wizard alternative\". (3) \"Why You Forget 80% of What You Study at Poker\" — supporting article, 1200 words, targets \"poker forgetting curve\". (4) \"Upswing Poker vs Grindlab\" — alternative page, 1000 words. Each includes: SEO-optimized title, meta description, internal links, CTA, written in Phil's voice.",
    priority="high",
    assigned_to="claude",
    due_date="2026-03-28",
    channel_id=ch_content_blog,
    estimated_hours=3.0,
    existing_id=24,
    blocker_note="/blog route must exist first.",
)

# Task 97 exists: "Spec Poker Room Review Page for Clint (/rooms Route)" — UPDATE
upsert_task(
    title="Add /rooms/[slug] route to Next.js",
    description="Same MDX structure as blog. Room Reports at /rooms/[city]-[room-name]. Frontmatter: room name, city, state, stakes, games, rating, date visited. Auto-added to sitemap. \"Rooms\" nav link should go to /rooms index page listing all published room reports.",
    priority="medium",
    assigned_to="clint",
    due_date="2026-04-07",
    channel_id=ch_technical,
    estimated_hours=3.0,
    existing_id=97,
    blocker_note="Blog infrastructure should be built first (same pattern).",
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 4: BACKLINK & OUTREACH ENGINE (March 9-ongoing)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 4: BACKLINK & OUTREACH ENGINE ──")

upsert_task(
    title="Research and draft podcast guest pitches",
    description="Target podcasts: DAT Poker, Thinking Poker, Just Hands, RecPoker, Chasing Poker Greatness, Poker Life Podcast, The Breakdown Poker, Only Friends, Cracking Aces. Claude researches each show (format, host, recent episodes, guest style) and writes personalized pitch email for each. Story angle: \"55-year-old live player building a study tool, about to do a cross-country poker road trip.\" Phil reviews, adds personal touch, sends from his email. Goal: 3-5 appearances in first 3 months.",
    priority="high",
    assigned_to="claude",
    due_date="2026-03-15",
    channel_id=ch_outreach,
    estimated_hours=1.5,
    status="this_week",
)

upsert_task(
    title="Create TwoPlusTwo forum account and first value post",
    description="Create account on TwoPlusTwo.com. Post in Software forum: \"Building a poker study app — here's what I've learned about how most players study\" (value post, not promotional). Add signature with grindlab.ai link. This generates a permanent backlink from a high-authority poker domain. Claude drafts the post. Phil posts manually.",
    priority="medium",
    assigned_to="phil",
    due_date="2026-03-22",
    channel_id=ch_forum,
    estimated_hours=0.25,
)

upsert_task(
    title="Build 2p2_daily_brief.py (Scotty)",
    description="Same architecture as reddit_daily_brief.py. Scans TwoPlusTwo Strategy and Software forums for engagement opportunities. Uses public page scraping (no API). Scores by relevance. Generates draft replies via OpenRouter/Haiku. Delivers to Telegram. Phil edits and posts manually. Cron: daily 7:30AM.",
    priority="medium",
    assigned_to="claude_code",
    due_date="2026-04-07",
    channel_id=ch_automation,
    estimated_hours=3.0,
    blocker_note="TwoPlusTwo account must exist first.",
)

upsert_task(
    title="Room Report backlink outreach template",
    description="Template email to poker room marketing contacts after publishing a Room Report. \"I wrote an honest review of [Room] after playing there last week. Here's the link: [URL]. Feel free to share it with your players or link from your site.\" Claude provides template. Phil personalizes one line per room and sends. Expected: 30-50% share on social, 10-20% link from website.",
    priority="medium",
    assigned_to="claude",
    due_date="2026-04-07",
    channel_id=ch_outreach,
    estimated_hours=0.25,
    blocker_note="First Room Report must be published.",
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 5: SCOTTY AUTOMATION BUILDS (April)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 5: SCOTTY AUTOMATION BUILDS ──")

upsert_task(
    title="Build technical_seo_monitor.py (Scotty)",
    description="Weekly cron. Crawls grindlab.ai pages. Checks: broken links (404s), missing meta descriptions, missing canonical tags, missing OG tags, page load time (via curl timing), missing alt text on images. Alerts via Telegram with specific page + issue. Runs Monday 6AM.",
    priority="high",
    assigned_to="claude_code",
    due_date="2026-04-07",
    channel_id=ch_automation,
    estimated_hours=3.0,
)

upsert_task(
    title="Build search_console_digest.py (Scotty)",
    description="Weekly cron. Connects to Google Search Console API. Pulls: top queries by impressions, \"almost ranking\" keywords (position 8-20), new keywords appearing, CTR by page. Formats as Telegram digest with keyword opportunities for Claude to use in blog calendar. Runs Wednesday 6AM.",
    priority="high",
    assigned_to="claude_code",
    due_date="2026-04-21",
    channel_id=ch_automation,
    estimated_hours=3.0,
    blocker_note="Google Search Console API access (service account key). Clint or Phil must set up GSC property and generate API credentials.",
)

upsert_task(
    title="Build backlink_monitor.py (Scotty)",
    description="Weekly cron. Uses free backlink check APIs or web scraping to monitor new/lost backlinks to grindlab.ai. Tracks domain authority growth over time. Telegram alert for new backlinks (celebrate) and lost backlinks (investigate). Runs Tuesday 6AM.",
    priority="medium",
    assigned_to="claude_code",
    due_date="2026-04-14",
    channel_id=ch_automation,
    estimated_hours=2.0,
)

upsert_task(
    title="Build content_gap_alert.py (Scotty)",
    description="Daily cron. Checks: blog post cadence (alert if <2 published this week by Friday), Buffer queue depth (alert if <3 days of content scheduled), Room Report cadence (alert if Phil visited a room but no report published within 7 days). Telegram alerts. Runs daily 8AM.",
    priority="medium",
    assigned_to="claude_code",
    due_date="2026-04-14",
    channel_id=ch_automation,
    estimated_hours=1.0,
    blocker_note="Blog must be live first.",
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 6: LEAD MAGNETS (April-May)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 6: LEAD MAGNETS ──")

# Task 50 exists: "Tilt Assessment quiz" — UPDATE with full details
upsert_task(
    title="Build Tilt Assessment quiz",
    description="Same architecture as Leak Finder. Different entry point — targets players who identify with mental game problems, not study problems. Opens a second door into the funnel. URL: /tools/tilt-assessment. SEO target: \"poker tilt test\". 10 questions about emotional patterns at the table. AI-generated report with tilt profile + specific strategies. Email capture. Feeds into Kit nurture.",
    priority="high",
    assigned_to="clint",
    due_date="2026-04-21",
    channel_id=ch_lead_magnets,
    estimated_hours=7.0,
    existing_id=50,
    blocker_note="Leak Finder pipeline must be documented so Clint can replicate.",
)

upsert_task(
    title="Add Leak Finder share mechanic",
    description="When someone completes the Leak Finder quiz and gets their report, add: \"Share your results\" button with pre-written tweet/post (\"I scored [X] on the Grindlab Leak Finder. What's your score? [link]\"), \"Challenge a friend\" option (personalized share link via text/email), OG image generation showing the user's score for rich link previews. This is the viral loop — quiz results are inherently shareable.",
    priority="high",
    assigned_to="clint",
    due_date="2026-03-28",
    channel_id=ch_lead_magnets,
    estimated_hours=4.0,
)

upsert_task(
    title="Build SparkLoop referral visibility",
    description="SparkLoop referral currently only visible in emails 1, 3, 6. Add visibility: on quiz thank-you page (\"Share with a friend, get a free guide\"), standalone /refer page for easy linking, in-app \"Refer a friend\" link (post-launch). The referral program exists — it just needs to be visible outside of email.",
    priority="medium",
    assigned_to="clint",
    due_date="2026-04-07",
    channel_id=ch_lead_magnets,
    estimated_hours=2.0,
)

# ═══════════════════════════════════════════════════════════════════
# PHASE 7: YOUTUBE SEO (April-ongoing)
# ═══════════════════════════════════════════════════════════════════
print("\n── PHASE 7: YOUTUBE SEO & ADS ──")

upsert_task(
    title="Film first long-form YouTube video (Caddy Corner)",
    description="\"How to Study Poker (The 5-Stage System)\" — 8-12 minute Caddy Corner video. Same content as the pillar blog post, delivered as video. YouTube SEO: keyword-targeted title, 500-word description with timestamps and links, chapter markers. This video and the blog post reinforce each other in search. Phil films during weekly batch session. Editing: either Phil does minimal cuts in Riverside.fm or hire second Fiverr editor for long-form ($40-80/video).",
    priority="medium",
    assigned_to="phil",
    due_date="2026-04-14",
    channel_id=ch_youtube,
    estimated_hours=1.0,
    blocker_note="Blog pillar post should be published first so video description links to it.",
)

upsert_task(
    title="Set up Meta Ads Manager retargeting audiences",
    description="Meta Pixel is installed. Before spending any ad money, define these audiences: (1) Visited /leakfinder but didn't complete quiz, (2) Completed quiz but didn't enter email, (3) Visited pricing but didn't start trial, (4) Blog readers who didn't take quiz. No ad spend — just audience definitions ready for when ads launch.",
    priority="medium",
    assigned_to="phil",
    due_date="2026-03-21",
    channel_id=ch_paid_ads,
    estimated_hours=0.5,
)

# ═══════════════════════════════════════════════════════════════════
# ONGOING RECURRING TASKS
# ═══════════════════════════════════════════════════════════════════
print("\n── ONGOING RECURRING TASKS ──")

upsert_task(
    title="Weekly blog post drafting (Claude)",
    description="Claude maintains the blog editorial calendar based on keyword architecture and Search Console data. Drafts full 1000-2000 word articles in Phil's voice. SEO-optimized. Phil reviews and approves in ~10 min each. Starts after blog infrastructure is live. 2x per week (Wednesday + Sunday).",
    priority="high",
    assigned_to="claude",
    due_date=None,
    channel_id=ch_content_blog,
    estimated_hours=0.25,
    status="recurring",
    recurring_frequency="weekly",
    blocker_note="Blog route must be built.",
)

upsert_task(
    title="Weekly outreach batch (Claude + Phil)",
    description="Every Monday, Claude delivers: 5 influencer emails, 2 podcast pitches, any poker room follow-ups from last week. Each email personalized to recipient's recent content. Phil reviews, adds one personal sentence, sends. Follow-ups auto-generated 7 days after no response.",
    priority="high",
    assigned_to="claude",
    due_date=None,
    channel_id=ch_outreach,
    estimated_hours=0.35,
    status="recurring",
    recurring_frequency="weekly",
)

upsert_task(
    title="Room Report writing (Claude + Phil)",
    description="Every poker room Phil visits gets a published Room Report. Phil records 5 min voice note with observations. Claude writes 1000-word report at /rooms/[slug]. Phil approves. Clint publishes (or Phil merges PR). Then Phil sends backlink outreach email to room's marketing contact.",
    priority="medium",
    assigned_to="claude",
    due_date=None,
    channel_id=ch_content_blog,
    estimated_hours=0.25,
    status="recurring",
    recurring_frequency=None,
    blocker_note="/rooms route must exist.",
)

conn.commit()

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

print(f"\n  CREATED: {len(created)} tasks")
for tid, title in created:
    print(f"    #{tid}: {title}")

print(f"\n  UPDATED: {len(updated)} tasks")
for tid, title in updated:
    print(f"    #{tid}: {title}")

print(f"\n  SKIPPED: {len(skipped)} tasks")
for reason, title in skipped:
    print(f"    {title} — {reason}")

# Category counts
print("\n  TASKS BY CATEGORY (channel):")
cur.execute("""
    SELECT c.name, COUNT(t.id) as cnt
    FROM tasks t
    JOIN channels c ON t.channel_id = c.id
    WHERE t.status NOT IN ('archived', 'done')
    GROUP BY c.name
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f"    {row['name']}: {row['cnt']}")

# Also count tasks with no channel
cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE channel_id IS NULL AND status NOT IN ('archived', 'done')")
no_ch = cur.fetchone()["cnt"]
if no_ch:
    print(f"    (No category): {no_ch}")

# First 5 by due date
print("\n  FIRST 5 TASKS BY DUE DATE (what Phil should work on first):")
cur.execute("""
    SELECT t.id, t.title, t.due_date, t.assigned_to, t.priority, COALESCE(c.name, '—') as cat
    FROM tasks t
    LEFT JOIN channels c ON t.channel_id = c.id
    WHERE t.status NOT IN ('done', 'archived', 'recurring')
      AND t.due_date IS NOT NULL
    ORDER BY t.due_date ASC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"    {row['due_date']} | #{row['id']} | {row['title']} [{row['priority']}] → {row['assigned_to']} ({row['cat']})")

if new_channels:
    print(f"\n  NEW CATEGORIES CREATED: {len(new_channels)}")
    for ch in new_channels:
        print(f"    - {ch}")

conn.close()
print("\nDone.")
