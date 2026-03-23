#!/bin/bash
# MCC Daily Backup — auto-commit code + backup database
# Runs via cron: 0 3 * * *
# Registered as an Automation in MCC for health monitoring

set -euo pipefail

# Ensure Homebrew binaries (git, gh, python3) are on PATH for cron
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

MCC_DIR="$HOME/marketing-command-center"
BACKUP_DIR="$MCC_DIR/data/backups"
LOG_FILE="$MCC_DIR/data/backups/backup.log"
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure directories exist
mkdir -p "$BACKUP_DIR"

log "=== Daily backup starting ==="

# --- 1. Database backup ---
DB_FILE="$MCC_DIR/data/mcc.db"
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_DIR/mcc_${TIMESTAMP}.db"
    log "Database backed up to mcc_${TIMESTAMP}.db"

    # Keep only last 14 daily backups
    ls -t "$BACKUP_DIR"/mcc_*.db 2>/dev/null | tail -n +15 | xargs -r rm
    log "Pruned old backups (keeping 14)"
else
    log "WARNING: Database file not found at $DB_FILE"
fi

# --- 2. Git auto-commit and push ---
cd "$MCC_DIR"

# Stage all tracked changes (respects .gitignore)
git add -A

# Only commit if there are staged changes
if git diff --cached --quiet; then
    log "No code changes to commit"
else
    git commit -m "Daily auto-backup ${TODAY}"
    log "Committed changes"
fi

# Push to origin using gh token (keyring unavailable in cron)
GH_TOKEN=$(gh auth token 2>/dev/null || echo "")
if [ -n "$GH_TOKEN" ]; then
    git -c "url.https://x-access-token:${GH_TOKEN}@github.com/.insteadOf=https://github.com/" \
        push origin main 2>&1 && log "Pushed to GitHub" \
        || log "WARNING: Push failed — will retry next run"
else
    log "WARNING: No gh token available — push skipped"
fi

# --- 3. Send heartbeat to MCC (if server is running) ---
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
        -d '{"status":"online","message":"Daily backup completed successfully"}' \
        > /dev/null 2>&1 && log "Heartbeat sent to MCC" || log "MCC server not reachable (heartbeat skipped)"

    # Report backup metric
    BACKUP_SIZE=$(du -k "$BACKUP_DIR/mcc_${TIMESTAMP}.db" 2>/dev/null | cut -f1 || echo "0")
    curl -s -X POST "http://localhost:5050/api/tools/metrics" \
        -H "X-Api-Key: $SCOTTY_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"metrics\":[{\"metric_name\":\"backup_size_kb\",\"value\":$BACKUP_SIZE,\"unit\":\"kb\"}]}" \
        > /dev/null 2>&1 || true
fi

log "=== Daily backup complete ==="
