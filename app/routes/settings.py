"""Settings — Remote Operation Mode, system health, pre-travel checklist."""
import os
import subprocess
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, Automation, AutomationHealth, HostingLocation,
    AutonomousTool, AutonomousToolHealth,
)
from app.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HEALTHCHECKS_PING_URL,
)
from app.alerts import test_telegram, test_healthchecks, ping_healthchecks

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="app/templates")


def _check_caffeinate() -> dict:
    """Check if caffeinate is running (sleep prevention)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "caffeinate -s"],
            capture_output=True, text=True, timeout=5
        )
        running = result.returncode == 0
        return {"running": running, "pid": result.stdout.strip() if running else None}
    except Exception:
        return {"running": False, "pid": None}


def _check_cron_job(pattern: str) -> bool:
    """Check if a cron job matching pattern exists."""
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        return pattern in result.stdout
    except Exception:
        return False


def _check_ssh() -> bool:
    """Check if SSH remote login is enabled."""
    try:
        result = subprocess.run(
            ["systemsetup", "-getremotelogin"],
            capture_output=True, text=True, timeout=5
        )
        return "on" in result.stdout.lower()
    except Exception:
        return False


def _last_git_commit_age() -> float | None:
    """Hours since last git commit."""
    try:
        result = subprocess.run(
            ["git", "-C", os.path.expanduser("~/marketing-command-center"),
             "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            ts = int(result.stdout.strip())
            return round((datetime.utcnow().timestamp() - ts) / 3600, 1)
    except Exception:
        pass
    return None


@router.get("/")
def settings_page(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()

    # Automation hosting breakdown
    automations = []
    mac_mini_autos = []
    cloud_autos = []
    if project:
        automations = db.query(Automation).filter_by(project_id=project.id).all()
        for a in automations:
            hosting = getattr(a, "hosting", None)
            if hosting and hosting.value == "cloud":
                cloud_autos.append(a)
            elif hosting and hosting.value == "hybrid":
                cloud_autos.append(a)  # survives partial
            else:
                mac_mini_autos.append(a)

    # Connected tools
    tools = []
    if project:
        tools = db.query(AutonomousTool).filter_by(
            project_id=project.id, is_active=True
        ).all()

    # System checks
    caffeinate = _check_caffeinate()
    heartbeat_cron = _check_cron_job("heartbeat_ping.sh")
    backup_cron = _check_cron_job("daily_backup.sh")
    ssh_enabled = _check_ssh()
    last_commit_hours = _last_git_commit_age()

    # Config status
    telegram_configured = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    healthchecks_configured = bool(HEALTHCHECKS_PING_URL)

    # Staleness summary
    now = datetime.utcnow()
    stale_autos = [a for a in automations if a.health in (AutomationHealth.stale, AutomationHealth.failed)]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "project": project,
        "current_page": "settings",
        "today": date.today(),
        # Automation breakdown
        "automations": automations,
        "mac_mini_autos": mac_mini_autos,
        "cloud_autos": cloud_autos,
        "stale_autos": stale_autos,
        "tools": tools,
        # System checks
        "caffeinate": caffeinate,
        "heartbeat_cron": heartbeat_cron,
        "backup_cron": backup_cron,
        "ssh_enabled": ssh_enabled,
        "last_commit_hours": last_commit_hours,
        # Config
        "telegram_configured": telegram_configured,
        "healthchecks_configured": healthchecks_configured,
        "healthchecks_url": HEALTHCHECKS_PING_URL or "",
    })


@router.post("/test-telegram")
def run_test_telegram():
    """Test Telegram alert delivery."""
    result = test_telegram()
    if result["working"]:
        return HTMLResponse(
            '<span class="text-mcc-success text-xs font-medium">Sent — check Telegram</span>'
        )
    return HTMLResponse(
        f'<span class="text-mcc-critical text-xs font-medium">Failed: {result["error"]}</span>'
    )


@router.post("/test-healthchecks")
def run_test_healthchecks():
    """Test Healthchecks.io ping."""
    result = test_healthchecks()
    if result["working"]:
        return HTMLResponse(
            '<span class="text-mcc-success text-xs font-medium">Ping OK</span>'
        )
    return HTMLResponse(
        f'<span class="text-mcc-critical text-xs font-medium">Failed: {result["error"]}</span>'
    )


@router.post("/test-all")
def run_full_system_test(db: Session = Depends(get_db)):
    """Run comprehensive system test."""
    results = {}

    # 1. Caffeinate
    caff = _check_caffeinate()
    results["caffeinate"] = caff["running"]

    # 2. Heartbeat cron
    results["heartbeat_cron"] = _check_cron_job("heartbeat_ping.sh")

    # 3. Backup cron
    results["backup_cron"] = _check_cron_job("daily_backup.sh")

    # 4. Telegram
    tg = test_telegram()
    results["telegram"] = tg["working"]

    # 5. Healthchecks.io
    hc = test_healthchecks()
    results["healthchecks"] = hc["working"]

    # 6. MCC server (we're running, so yes)
    results["mcc_server"] = True

    # 7. Git backup age
    commit_hours = _last_git_commit_age()
    results["git_backup_recent"] = commit_hours is not None and commit_hours < 26

    # 8. Automations healthy
    project = db.query(Project).filter_by(slug="grindlab").first()
    if project:
        stale = db.query(Automation).filter(
            Automation.project_id == project.id,
            Automation.health.in_([AutomationHealth.stale, AutomationHealth.failed]),
        ).count()
        results["all_automations_healthy"] = stale == 0
    else:
        results["all_automations_healthy"] = False

    # 9. Connected tools healthy
    if project:
        now = datetime.utcnow()
        tools = db.query(AutonomousTool).filter_by(
            project_id=project.id, is_active=True
        ).all()
        tool_issues = 0
        for t in tools:
            if t.expected_heartbeat_hours and t.last_heartbeat:
                hours = (now - t.last_heartbeat).total_seconds() / 3600
                if hours > t.expected_heartbeat_hours:
                    tool_issues += 1
            elif t.expected_heartbeat_hours and not t.last_heartbeat:
                tool_issues += 1
        results["all_tools_healthy"] = tool_issues == 0
    else:
        results["all_tools_healthy"] = False

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    color = "text-mcc-success" if passed == total else (
        "text-mcc-warning" if passed >= total - 2 else "text-mcc-critical"
    )

    html_parts = [f'<div class="mb-2"><span class="{color} text-sm font-bold">{passed}/{total} checks passed</span></div>']
    labels = {
        "caffeinate": "Sleep prevention (caffeinate)",
        "heartbeat_cron": "Dead man's switch cron",
        "backup_cron": "Daily backup cron",
        "telegram": "Telegram alerts",
        "healthchecks": "Healthchecks.io ping",
        "mcc_server": "MCC server running",
        "git_backup_recent": "Git backup within 26h",
        "all_automations_healthy": "All automations healthy",
        "all_tools_healthy": "All connected tools healthy",
    }
    for key, label in labels.items():
        val = results.get(key, False)
        icon = "text-mcc-success" if val else "text-mcc-critical"
        symbol = "&#10003;" if val else "&#10007;"
        html_parts.append(
            f'<div class="flex items-center gap-2 py-1">'
            f'<span class="{icon} text-sm">{symbol}</span>'
            f'<span class="text-xs">{label}</span></div>'
        )

    return HTMLResponse("\n".join(html_parts))


@router.post("/install-caffeinate")
def install_caffeinate():
    """Install and start the caffeinate LaunchAgent."""
    plist_src = os.path.expanduser(
        "~/marketing-command-center/scripts/com.mcc.caffeinate.plist"
    )
    plist_dst = os.path.expanduser(
        "~/Library/LaunchAgents/com.mcc.caffeinate.plist"
    )
    try:
        import shutil
        shutil.copy2(plist_src, plist_dst)
        subprocess.run(["launchctl", "load", plist_dst], timeout=5)
        return HTMLResponse(
            '<span class="text-mcc-success text-xs font-medium">Installed &amp; started</span>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<span class="text-mcc-critical text-xs font-medium">Failed: {e}</span>'
        )
