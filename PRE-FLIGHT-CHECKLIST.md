# BEFORE YOU START — PRE-FLIGHT CHECKLIST

Run through this on your Mac Mini before opening Claude Code.
Each step takes 1-2 minutes. Total: ~15 minutes.

---

## 1. INSTALL CLAUDE CODE (if not already installed)

The native installer is now the recommended method. No Node.js needed.

```bash
# Install Claude Code native binary
curl -fsSL https://claude.ai/install.sh | bash

# Close and reopen terminal, then verify
claude --version
```

If you already have it via npm, migrate:
```bash
claude install          # installs native binary alongside npm version
npm uninstall -g @anthropic-ai/claude-code   # remove old npm version
```

**You need a paid plan.** Claude Pro ($20/mo), Max ($100-200/mo), or API credits via console.anthropic.com. Free plan does NOT include Claude Code access.

**For a build this size, Max is recommended** — you'll burn through Pro rate limits mid-phase. If using API credits instead, load $50-100 to be safe.

---

## 2. VERIFY PYTHON

```bash
python3 --version
# Should show 3.14.x (you have this on your Mac Mini)
```

If not found:
```bash
brew install python
```

---

## 3. CREATE THE PROJECT DIRECTORY

```bash
mkdir -p ~/marketing-command-center
cd ~/marketing-command-center
```

Copy the 4 files from your Desktop folder into this directory:
```bash
cp ~/Desktop/marketing-command-center/* ~/marketing-command-center/
```

Verify:
```bash
ls -la ~/marketing-command-center/
# Should show:
# MCC-COMPLETE-SPEC.md
# CLAUDE-CODE-KICKOFF.md
# CLAUDE-CODE-PHASE-PROMPTS.md
# README.md
```

---

## 4. CREATE A CLAUDE.md FILE

This is critical. Claude Code reads this file automatically on every session. It gives persistent context so you don't have to re-explain the project.

```bash
cat > ~/marketing-command-center/CLAUDE.md << 'EOF'
# Marketing Command Center (MCC)

## What This Is
A local marketing execution platform. Python/FastAPI + Jinja2/HTMX + SQLite.
Runs on localhost:5000. Dark theme. Single process. No Docker.

## Complete Spec
Read MCC-COMPLETE-SPEC.md for the full technical specification.
It contains ALL models, views, integrations, and build phases.

## Tech Stack
- Python 3.14 + FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN)
- SQLite via SQLAlchemy ORM (file: data/mcc.db)
- Chart.js + Sortable.js (CDN)
- Anthropic API for AI features (Claude Sonnet)

## Critical Rules
1. Server-rendered HTML + HTMX. No React/Vue/SPA.
2. SQLite only. No Postgres/Redis.
3. Single Python process. No Docker.
4. Missing API keys = graceful fallback, never crash.
5. Dark theme: bg #0F0F23, cards #1A1A2E, accent #E94560, text #F0F0F0.

## Build Order
Follow phases 1-10 in MCC-COMPLETE-SPEC.md Section 12.
Test each phase before proceeding to the next.

## First Project
Grindlab (poker study SaaS) is pre-loaded via seeds/grindlab.py.
All seed data is defined in MCC-COMPLETE-SPEC.md Section 10.
EOF
```

---

## 5. SET UP API KEYS

Create a `.env` file for the API keys you have right now. You can add more later.

```bash
cat > ~/marketing-command-center/.env << 'EOF'
# Required for AI features (chat, insights, scheduled jobs)
ANTHROPIC_API_KEY=

# Kit (ConvertKit) — v3 API Secret
CONVERTKIT_API_SECRET=

# Instantly
INSTANTLY_API_KEY=

# Google Analytics 4
GA4_CREDENTIALS_PATH=
GA4_PROPERTY_ID=

# Buffer
BUFFER_ACCESS_TOKEN=

# Stripe (post-launch, leave blank for now)
STRIPE_API_KEY=

# Ad platforms (set up when you run ads)
META_ADS_ACCESS_TOKEN=
REDDIT_ADS_TOKEN=
GOOGLE_ADS_CREDENTIALS=

# Optional
SPARKLOOP_API_KEY=
RAILWAY_API_KEY=
EOF
```

**Fill in what you have right now.** At minimum, get:
- `ANTHROPIC_API_KEY` — from console.anthropic.com → API Keys
- `CONVERTKIT_API_SECRET` — from Kit dashboard → Settings → General → API Secret
- `INSTANTLY_API_KEY` — from Instantly dashboard → Settings → API

The rest can be added later. The app works without any of them.

---

## 6. CHECK PORT 5000 IS FREE

```bash
lsof -i :5000
# Should return nothing. If something is running on 5000, kill it or
# change the port in .env: LAUNCH_COMMAND_PORT=5001
```

---

## 7. VERIFY NETWORK (for pip installs)

Claude Code will need to install Python packages. Make sure pip works:

```bash
pip3 install --break-system-packages --dry-run fastapi
# Should show what it WOULD install without errors
```

If this fails, you may need to:
```bash
pip3 install --break-system-packages --upgrade pip
```

---

## 8. SET UP A VIRTUAL ENVIRONMENT (optional but recommended)

Claude Code should do this in Phase 1, but creating it ahead of time avoids permission issues:

```bash
cd ~/marketing-command-center
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

---

## 9. OPEN CLAUDE CODE

```bash
cd ~/marketing-command-center
claude
```

If using a venv, activate it first:
```bash
cd ~/marketing-command-center
source venv/bin/activate
claude
```

---

## 10. PASTE THE KICKOFF PROMPT

Open `CLAUDE-CODE-KICKOFF.md` in any text editor. Copy everything under "PASTE THIS INTO CLAUDE CODE:" and paste it into Claude Code.

Then follow the phase-by-phase process in `CLAUDE-CODE-PHASE-PROMPTS.md`.

---

## TIPS FOR WORKING WITH CLAUDE CODE ON THIS BUILD

### Rate Limits
This is a large build. If you hit rate limits:
- Wait 5-10 minutes and continue
- Consider Claude Max ($100/mo) for higher limits
- Or use API credits via console.anthropic.com

### If Claude Code Loses Context
Paste this recovery prompt:
```
Read CLAUDE.md and MCC-COMPLETE-SPEC.md in this directory. 
We are building Marketing Command Center. 
We are currently on Phase [X]. 
Continue building from where we left off.
```

### If a Phase Fails Testing
Don't move to the next phase. Tell Claude Code:
```
Phase [X] has an issue: [describe what's wrong].
Fix this before we move on. Do not start Phase [X+1].
```

### If the Spec Is Too Long for Context
Tell Claude Code:
```
The full spec is in MCC-COMPLETE-SPEC.md but it's large. 
For this phase, focus only on Section [X] and Section [Y].
Don't try to hold the whole spec in memory.
```

### Save Progress Between Sessions
If you close Claude Code and come back later:
```
cd ~/marketing-command-center
source venv/bin/activate
claude
```
Then paste the recovery prompt above with the current phase number.

### Backup the Database
Once the app is running with real data:
```bash
cp ~/marketing-command-center/data/mcc.db ~/marketing-command-center/data/backups/mcc_$(date +%Y%m%d).db
```

---

## EXPECTED TIMELINE

| Phase | What | Estimated Time |
|-------|------|---------------|
| 1 | Foundation | 1-2 Claude Code sessions |
| 2 | Dashboard + Channels | 1-2 sessions |
| 3 | Tasks + Roadmap | 1-2 sessions |
| 4 | Daily + Calendar + Weekly | 1 session |
| 5 | Pipelines | 1-2 sessions |
| 6 | Ads + Stack + Budget + Working | 1-2 sessions |
| 7 | API Integrations | 2-3 sessions |
| 8 | AI Layer + Chat | 2-3 sessions |
| 9 | Strategy + Wizard + Knowledge | 2-3 sessions |
| 10 | Polish | 1-2 sessions |

A "session" is roughly 30-60 minutes of Claude Code working, depending on rate limits. Total: ~15-20 sessions over 1-2 weeks if you do 2-3 sessions per day.

You do NOT need to do this all at once. The phases are independent increments — after Phase 4, you already have a usable daily ops tool. Everything after that adds capability.

---

## MINIMUM VIABLE USAGE (After Phase 4)

Once Phases 1-4 are done, you have:
- Dashboard with execution score and channel health
- Task kanban with dependencies
- Timeline/roadmap with critical path
- Daily morning briefing
- Weekly review
- All Grindlab data pre-loaded

That's already more than enough to run your marketing operation. Phases 5-10 add depth, AI, and intelligence layers — build them as time allows.
