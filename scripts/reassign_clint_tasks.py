#!/usr/bin/env python3
"""Reassign all Clint tasks to Claude Code. Update categories and descriptions."""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/mcc.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

now = datetime.now(timezone.utc).isoformat()

# Channel IDs
CH_WEBSITE_SEO = 16
CH_TECHNICAL_CLINT = 20  # Being retired
CH_LEAD_MAGNETS = 21
CH_INFRA = None  # Will create if needed

# Get or create Infrastructure channel
cur.execute("SELECT id FROM channels WHERE name = 'Infrastructure'")
row = cur.fetchone()
if row:
    CH_INFRA = row["id"]
else:
    cur.execute(
        """INSERT INTO channels (project_id, name, channel_type, status, automation_level, owner, health, created_at, updated_at)
           VALUES (1, 'Infrastructure', 'owned', 'active', 'manual', 'phil', 'good', ?, ?)""",
        (now, now),
    )
    conn.commit()
    CH_INFRA = cur.lastrowid
    print(f"[NEW CHANNEL] #{CH_INFRA}: Infrastructure")

WORKFLOW_NOTE = "\n\nWORKFLOW: Claude Code builds this. Phil runs the Claude Code session, reviews the PR, merges, and Vercel auto-deploys from main."

reassigned = []

def update_task(task_id, title=None, description=None, assigned_to="claude_code", channel_id=None):
    """Update a task with new values."""
    parts = ["assigned_to = ?", "updated_at = ?"]
    params = [assigned_to, now]

    if title:
        parts.append("title = ?")
        params.append(title)
    if description:
        parts.append("description = ?")
        params.append(description)
    if channel_id:
        parts.append("channel_id = ?")
        params.append(channel_id)

    params.append(task_id)
    sql = f"UPDATE tasks SET {', '.join(parts)} WHERE id = ?"
    cur.execute(sql, params)
    reassigned.append((task_id, title or "(title unchanged)"))


# ═══════════════════════════════════════════════════════════════
# SPECIFIC TASK UPDATES (with detailed new descriptions)
# ═══════════════════════════════════════════════════════════════

# #117 — Add sitemap.xml
update_task(117,
    title="Add sitemap.xml to grindlab.ai",
    description="Claude Code session. Install next-sitemap package in the Next.js Pages Router project. Create next-sitemap.config.js at project root. Configure to auto-generate sitemap.xml on each build. Include all current routes: /, /leakfinder, /contact, /privacy-policy, /terms-of-service, /cookie-policy. Configure to auto-discover future /blog/* and /rooms/* routes. Add postbuild script to package.json. Test locally, create PR, Phil merges. Vercel auto-deploys." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #117: Add sitemap.xml to grindlab.ai")

# #118 — Add Sitemap to robots.txt
update_task(118,
    title="Add Sitemap reference to robots.txt",
    description="Claude Code session. Check if robots.txt is served from the Next.js public/ directory or managed by Cloudflare. If it's in public/, add 'Sitemap: https://grindlab.ai/sitemap.xml' to the file. If Cloudflare manages it, Phil needs to add the sitemap reference in Cloudflare dashboard (note this in the task as a blocker). The current robots.txt allows Googlebot via Content-Signal: search=yes — do NOT change that. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #118: Add Sitemap reference to robots.txt")

# #119 — Add canonical tags
update_task(119,
    title="Add canonical tags to all pages",
    description="Claude Code session. In the Next.js _app.js or individual page files, add <link rel='canonical' href='https://www.grindlab.ai/[path]'> to every page using next/head. Homepage already has one — verify it's correct. /leakfinder is MISSING one — add it. Create a reusable SEO component that auto-generates canonical from the current route. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #119: Add canonical tags to all pages")

# #120 — Add structured data
update_task(120,
    title="Add structured data (schema markup) to homepage and leakfinder",
    description="Claude Code session. Add JSON-LD structured data to pages using next/head or a custom Script component. Homepage: Organization schema + WebSite schema with SearchAction + FAQPage schema (7 FAQ items already on the page — extract the Q&A pairs). /leakfinder: Quiz schema or SoftwareApplication schema. Create a reusable JsonLd component that accepts schema type and data. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #120: Add structured data (schema markup)")

# #123 — Option B copy refresh (rename from "Clint implements...")
update_task(123,
    title="Implement Option B copy refresh (Claude Code)",
    description="Claude Code session. Replace homepage copy with the approved Option B text. Changes: hero headline, sub-headline, CTA button text (waitlist → trial), feature section framing, pricing section copy, footer copy. No layout changes. No URL changes. Phil provides the exact approved copy before this session runs. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #123: Implement Option B copy refresh (Claude Code)")

# #124 — Blog route (rename from "Clint adds /blog route")
update_task(124,
    title="Build /blog infrastructure (Claude Code)",
    description="Claude Code session (larger — may need 2 sessions). Add /blog/[slug] dynamic route to Next.js Pages Router. Blog posts stored as MDX files in /content/blog/ directory. Each MDX file has frontmatter: title, description, date, author, keywords, cta_type (quiz/email/trial), slug. Build: MDX processing with next-mdx-remote or similar, auto-generated meta tags from frontmatter, breadcrumb navigation component, related posts component (simple — 2-3 links based on shared keywords), configurable CTA component, Article JSON-LD schema auto-generated from frontmatter, /blog index page listing all posts sorted by date. Posts auto-included in sitemap via next-sitemap. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #124: Build /blog infrastructure (Claude Code)")

# #97 — /rooms route (rename)
update_task(97,
    title="Build /rooms infrastructure (Claude Code)",
    description="Claude Code session. Same MDX pattern as /blog. Dynamic route at /rooms/[slug]. MDX files in /content/rooms/. Frontmatter: room_name, city, state, stakes, games_running, rating, date_visited, image. /rooms index page listing all published reports with city grouping. Each room page has: room details header, full review content, Leak Finder quiz CTA, map embed (optional, can add later). Auto-included in sitemap. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #97: Build /rooms infrastructure (Claude Code)")

# #133 — Leak Finder share mechanic
update_task(133,
    title="Add Leak Finder share mechanic",
    description="Claude Code session. On the Leak Finder results page (after quiz completion), add: (1) Social share buttons with pre-filled text: 'I scored [X] on the Grindlab Leak Finder. What's your score? https://grindlab.ai/leakfinder' (2) Copy-link button for easy sharing (3) If feasible, dynamic OG image that shows the user's score for rich link previews. Phil reviews the share copy before merging. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_LEAD_MAGNETS,
)
print(f"  [UPDATED] #133: Add Leak Finder share mechanic")

# #134 — SparkLoop referral visibility
update_task(134,
    title="Build SparkLoop referral visibility",
    description="Claude Code session. Add SparkLoop referral CTA to: (1) Quiz thank-you/results page — 'Share with a friend, get a free pre-session guide' (2) Create standalone /refer page that explains the 4 referral tiers and links to SparkLoop. (3) Add 'Refer a Friend' link to footer navigation. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_LEAD_MAGNETS,
)
print(f"  [UPDATED] #134: Build SparkLoop referral visibility")

# #121 — Secondary CTA
update_task(121,
    title="Add secondary CTA to homepage (Leak Finder quiz)",
    description="Claude Code session. Add a secondary CTA block below the first waitlist/trial form on the homepage. Copy: 'Not ready to commit? Take the free Leak Finder quiz — find your top 3 leaks in 3 minutes.' Green outlined button linking to /leakfinder. Also add a Leak Finder mention in the feature cards section. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #121: Add secondary CTA to homepage")

# #33 — Social proof
update_task(33,
    title="Add social proof element to homepage",
    description="Claude Code session. Add dynamic subscriber/quiz counter near the signup form. Options: (1) Hardcoded number updated via env var or content file — simplest. (2) API call to Kit for live subscriber count — more complex. Start with option 1. Text: 'Join [X]+ poker players on the waitlist' or post-launch 'Join [X]+ poker players improving their game'. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #33: Add social proof element to homepage")

# #48 — Title tag (already in Website/SEO, just update assignee + desc)
update_task(48,
    title="Optimize homepage title tag for SEO",
    description="Claude Code session. Change the page title from 'Grindlab — The Study Caddy for Poker Players' to the Phil-approved SEO title. Target keywords: 'poker study system', 'poker study app'. Recommended: 'Grindlab | Poker Study System — Learn, Retain, Recall Under Pressure'. Update in next/head or _document.js. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #48: Optimize homepage title tag for SEO")

# #47 — OG meta tags (was Clint, reassign)
update_task(47,
    title="Add OG meta tags to homepage and /leakfinder",
    description="Claude Code session. Add Open Graph and Twitter Card meta tags to all pages. Include: og:title, og:description, og:image, og:url, twitter:card, twitter:title, twitter:description. Create a reusable OG component. Use page-specific images where available. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #47: Add OG meta tags")

# #50 — Tilt Assessment quiz (lead magnet, complex — keep Claude Code but note it's bigger)
update_task(50,
    title="Build Tilt Assessment quiz",
    description="Claude Code session (larger build). Same architecture as Leak Finder. Different entry point — targets players who identify with mental game problems. URL: /tools/tilt-assessment. SEO target: 'poker tilt test'. 10 questions about emotional patterns at the table. AI-generated report with tilt profile + specific strategies. Email capture. Feeds into Kit nurture. Claude Code implements using the same pipeline as Leak Finder. Create PR, Phil merges." + WORKFLOW_NOTE
    + "\n\nBLOCKER: Leak Finder pipeline must be documented so the pattern can be replicated.",
    channel_id=CH_LEAD_MAGNETS,
)
print(f"  [UPDATED] #50: Build Tilt Assessment quiz")

# #11 — Stripe: This is PRODUCT work, not marketing. Keep Clint.
# The user said "ALL marketing-side website changes" are Claude Code.
# Stripe is product/backend. Leave assigned_to as clint, move to Infrastructure.
cur.execute("UPDATE tasks SET channel_id = ?, updated_at = ? WHERE id = 11", (CH_INFRA, now))
print(f"  [KEPT CLINT] #11: Set up Stripe payment integration (product work, not marketing)")

# #15 — Meta Pixel: Already done, just reassign for consistency
update_task(15,
    description="Meta Pixel installed on all pages. Completed." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #15: Set up Meta Pixel (already done, reassigned)")

# #40 — Optimize Leak Finder quiz load time: This is app performance
update_task(40,
    title="Optimize Leak Finder quiz load time",
    description="Claude Code session. Audit /leakfinder page load performance. Check bundle size, image optimization, lazy loading. Optimize where possible. Create PR, Phil merges." + WORKFLOW_NOTE,
    channel_id=CH_WEBSITE_SEO,
)
print(f"  [UPDATED] #40: Optimize Leak Finder quiz load time")

conn.commit()

# ═══════════════════════════════════════════════════════════════
# Now retire the "Technical (Clint)" channel — move any remaining tasks
# ═══════════════════════════════════════════════════════════════
cur.execute("SELECT id, title FROM tasks WHERE channel_id = 20")
remaining = cur.fetchall()
if remaining:
    print(f"\n  [CLEANUP] Moving {len(remaining)} remaining tasks from 'Technical (Clint)' to 'Website / SEO':")
    for r in remaining:
        cur.execute("UPDATE tasks SET channel_id = ?, updated_at = ? WHERE id = ?", (CH_WEBSITE_SEO, now, r["id"]))
        print(f"    #{r['id']}: {r['title']}")
    conn.commit()

# ═══════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

# 1. Total reassigned
print(f"\n  1. TOTAL TASKS REASSIGNED FROM CLINT TO CLAUDE CODE: {len(reassigned)}")
# Note: #11 kept as Clint
print(f"     (Task #11 Stripe kept with Clint — product work, not marketing)")

# 2. Updated task list by due date (first 10 non-done)
print("\n  2. FIRST 10 TASKS BY DUE DATE:")
cur.execute("""
    SELECT t.id, t.title, t.due_date, t.assigned_to, t.priority, t.status, COALESCE(c.name, '—') as cat
    FROM tasks t
    LEFT JOIN channels c ON t.channel_id = c.id
    WHERE t.status NOT IN ('done', 'archived', 'recurring')
      AND t.due_date IS NOT NULL
    ORDER BY t.due_date ASC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"     {row['due_date']} | #{row['id']} [{row['status']}] {row['title']} ({row['priority']}) → {row['assigned_to']} | {row['cat']}")

# 3. Any tasks still referencing Clint in title or description
print("\n  3. TASKS STILL REFERENCING 'CLINT' IN TITLE OR DESCRIPTION:")
cur.execute("""
    SELECT id, title FROM tasks
    WHERE (title LIKE '%Clint%' OR title LIKE '%clint%'
       OR description LIKE '%Clint implements%' OR description LIKE '%Clint does%'
       OR description LIKE '%Clint adds%' OR description LIKE '%Clint can%')
      AND status NOT IN ('done', 'archived')
""")
clint_refs = cur.fetchall()
if clint_refs:
    for r in clint_refs:
        print(f"     #{r['id']}: {r['title']}")
else:
    print(f"     None found — clean!")

# 4. Any tasks still in "Technical (Clint)" category
print("\n  4. TASKS IN 'TECHNICAL (CLINT)' CATEGORY:")
cur.execute("SELECT id, title FROM tasks WHERE channel_id = 20 AND status NOT IN ('done', 'archived')")
tech_clint = cur.fetchall()
if tech_clint:
    for r in tech_clint:
        print(f"     #{r['id']}: {r['title']}")
else:
    print(f"     None — category fully retired!")

# 5. Assignee still clint?
print("\n  5. TASKS STILL ASSIGNED TO 'CLINT':")
cur.execute("SELECT id, title, status FROM tasks WHERE assigned_to LIKE '%clint%' AND status NOT IN ('done', 'archived')")
still_clint = cur.fetchall()
for r in still_clint:
    print(f"     #{r['id']}: {r['title']} [{r['status']}]")
if not still_clint:
    print(f"     None (all reassigned)")

conn.close()
print("\nDone.")
