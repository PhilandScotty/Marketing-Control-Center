# CLAUDE CODE KICKOFF PROMPT
# Copy everything below this line into Claude Code as your first message.
# Make sure MCC-COMPLETE-SPEC.md is in the working directory first.

---

## PASTE THIS INTO CLAUDE CODE:

Read the file `MCC-COMPLETE-SPEC.md` in this directory. It is the complete technical specification for a project called Marketing Command Center (MCC).

**What MCC is:** A local desktop marketing execution platform built with Python/FastAPI that runs on localhost:5000. It tracks channels, tasks, automations, metrics, ads, content, outreach, subscribers, and more — with AI-powered monitoring that prevents anything from falling through the cracks. Dark theme, polished UI, server-rendered with HTMX.

**Your job:** Build MCC following the spec exactly, phase by phase (Section 12). Each phase produces a testable increment. After each phase, stop and confirm it works before moving to the next.

**Critical rules:**
1. Python 3.14 + FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN). No React, no Vue, no SPA.
2. SQLite via SQLAlchemy. No Postgres, no Redis.
3. Single Python process. No Docker.
4. Dark theme per Section 6. This is not optional.
5. Missing API keys = graceful fallback to manual entry. Never crash.
6. Missing ANTHROPIC_API_KEY = no AI features but app fully functional.
7. All Grindlab seed data pre-loaded on first run (Section 10).
8. HTMX for all interactions — no full page reloads.

**Start with Phase 1: Foundation.**
Build: project structure, requirements.txt, database.py, ALL 26 models from Section 4, seeds/grindlab.py with all seed data from Section 10, run.py, and base.html with the full sidebar navigation and dark theme.

When Phase 1 is done and I can run `python run.py` and see the base page at localhost:5000 with the sidebar and Grindlab loaded, tell me and we'll move to Phase 2.
