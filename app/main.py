import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import get_db, init_db
from seeds.grindlab import seed_grindlab

from app.routes import (
    dashboard, channels, metrics, subscribers, ai, tasks, roadmap,
    daily, calendar_view, weekly, automations, pipelines, feedback,
    ads, techstack, budget, experiments, whats_working, api,
)
from app.routes import chat, strategy, knowledge, competitors, partner, retention, wizard, search
from app.routes import tools_api, tools_mgmt, settings
from app.routes import checklist, templates as templates_route, brand, track, strategy_export, discovery, intelligence, website
from app.routes import queue as queue_route
from app.routes import rd_lab
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)

_original_template_response = Jinja2Templates.TemplateResponse


def _compat_template_response(self, *args, **kwargs):
    """Support the repo's existing TemplateResponse(name, context) pattern."""
    if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        request = args[1].get("request")
        if request is None:
            raise ValueError("Template context must include request")
        return _original_template_response(self, request, args[0], args[1], *args[2:], **kwargs)
    return _original_template_response(self, *args, **kwargs)


Jinja2Templates.TemplateResponse = _compat_template_response

app = FastAPI(title="Marketing Command Center")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(channels.router)
app.include_router(metrics.router)
app.include_router(subscribers.router)
app.include_router(ai.router)
app.include_router(tasks.router)
app.include_router(roadmap.router)
app.include_router(daily.router)
app.include_router(calendar_view.router)
app.include_router(weekly.router)
app.include_router(automations.router)
app.include_router(pipelines.router)
app.include_router(feedback.router)
app.include_router(ads.router)
app.include_router(techstack.router)
app.include_router(budget.router)
app.include_router(experiments.router)
app.include_router(whats_working.router)
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(strategy.router)
app.include_router(knowledge.router)
app.include_router(competitors.router)
app.include_router(partner.router)
app.include_router(retention.router)
app.include_router(wizard.router)
app.include_router(search.router)
app.include_router(tools_api.router)
app.include_router(tools_mgmt.router)
app.include_router(settings.router)
app.include_router(checklist.router)
app.include_router(templates_route.router)
app.include_router(brand.router)
app.include_router(track.router)
app.include_router(strategy_export.router)
app.include_router(discovery.router)
app.include_router(intelligence.router)
app.include_router(website.router)
app.include_router(queue_route.router)
app.include_router(rd_lab.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return user-friendly error messages instead of stack traces."""
    logger = logging.getLogger("mcc")
    logger.exception(f"Unhandled error on {request.url}: {exc}")

    # For HTMX requests, return a small error fragment
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<div class="text-center py-4 text-sm text-mcc-critical">'
            'Something went wrong. Please try again.</div>',
            status_code=500,
        )

    # For full page loads, return a styled error page
    return HTMLResponse(
        '<!DOCTYPE html><html><head><title>Error - MCC</title>'
        '<script src="https://cdn.tailwindcss.com"></script>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">'
        '</head>'
        '<body class="bg-[#0B0B1A] text-[#E8E8F0] min-h-screen flex items-center justify-center" style="font-family:Inter,sans-serif">'
        '<div class="text-center"><h1 class="text-2xl font-semibold mb-2">Something went wrong</h1>'
        '<p class="text-[#6B6B8A] mb-4">An unexpected error occurred.</p>'
        '<a href="/" class="text-[#06B6D4] hover:underline">Back to Dashboard</a></div>'
        '</body></html>',
        status_code=500,
    )


@app.on_event("startup")
def startup():
    init_db()
    db = next(get_db())
    try:
        seed_grindlab(db)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    stop_scheduler()
