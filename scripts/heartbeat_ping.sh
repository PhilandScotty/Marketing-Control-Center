#!/bin/bash
# Dead Man's Switch — pings Healthchecks.io every 30 minutes
# If this stops, Healthchecks.io emails/SMS alerts Phil
# Runs via cron: */30 * * * *
#
# This is the LAST LINE OF DEFENSE. If this stops pinging:
# - Mac Mini crashed, lost power, lost internet, went to sleep, or cron died
# - Phil gets alerted by Healthchecks.io (external to Mac Mini)

set -euo pipefail

MCC_DIR="$HOME/marketing-command-center"

# Load the Healthchecks.io ping URL from .env or config
if [ -f "$MCC_DIR/.env" ]; then
    HEALTHCHECKS_PING_URL=$(grep -E '^HEALTHCHECKS_PING_URL=' "$MCC_DIR/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "")
fi
HEALTHCHECKS_PING_URL="${HEALTHCHECKS_PING_URL:-}"

if [ -z "$HEALTHCHECKS_PING_URL" ]; then
    # Try reading from Python config as fallback
    HEALTHCHECKS_PING_URL=$(python3 -c "
import os, sys
sys.path.insert(0, '$MCC_DIR')
url = os.getenv('HEALTHCHECKS_PING_URL', '')
print(url)
" 2>/dev/null || echo "")
fi

if [ -z "$HEALTHCHECKS_PING_URL" ]; then
    echo "[$(date)] ERROR: HEALTHCHECKS_PING_URL not configured" >&2
    exit 1
fi

# Ping Healthchecks.io
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$HEALTHCHECKS_PING_URL" --max-time 10 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    # Success — also try to update MCC if server is running
    # This confirms both the Mac Mini AND the heartbeat script are alive
    SCOTTY_API_KEY=$(python3 -c "
import sys
sys.path.insert(0, '$MCC_DIR')
from app.database import init_db, get_db
from app.models import AutonomousTool
init_db()
db = next(get_db())
tool = db.query(AutonomousTool).filter_by(name='Scotty', is_active=True).first()
print(tool.api_key if tool else '')
db.close()
" 2>/dev/null || echo "")

    if [ -n "$SCOTTY_API_KEY" ]; then
        curl -s -X POST "http://localhost:5050/api/tools/heartbeat" \
            -H "X-Api-Key: $SCOTTY_API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"status":"online","message":"Dead man switch ping OK"}' \
            > /dev/null 2>&1 || true
    fi
else
    echo "[$(date)] WARNING: Healthchecks.io ping failed (HTTP $HTTP_STATUS)" >&2
fi
