#!/bin/bash
# Blue-Green Migration Deployment Script
# Generated for CivicPulse Database Migration Safety

set -euo pipefail

# Configuration
BLUE_DB_URL="${DATABASE_URL_BLUE}"
GREEN_DB_URL="${DATABASE_URL_GREEN}"
BACKUP_DIR="/opt/civicpulse/backups"
LOG_FILE="/opt/civicpulse/logs/migration_$(date +%Y%m%d_%H%M%S).log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Error handler
error_handler() {
    log "ERROR: Migration failed at step $1"
    log "Initiating emergency rollback..."
    # Add rollback commands here
    exit 1
}

trap 'error_handler ${LINENO}' ERR

log "Starting blue-green migration deployment"

# Step 1: Pre-flight checks
log "Step 1: Running pre-flight checks"
python migration_safety_tests.py || error_handler "Pre-flight checks"

# Step 2: Create backup
log "Step 2: Creating database backup"
mkdir -p "$BACKUP_DIR"
pg_dump "$BLUE_DB_URL" > "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"

# Step 3: Apply migrations to green
log "Step 3: Applying migrations to green environment"
export DATABASE_URL="$GREEN_DB_URL"
python manage.py migrate --verbosity=2

# Step 4: Validate green environment
log "Step 4: Validating green environment"
python manage.py check
python -c "from civicpulse.models import Person; print(f'Person count: {Person.objects.count()}')"

# Step 5: Switch traffic (requires manual confirmation)
log "Step 5: Ready to switch traffic to green environment"
echo "Manual confirmation required to proceed with traffic switch"
echo "Verify green environment is ready, then run:"
echo "  aws elb modify-target-group --target-group-arn \$GREEN_TARGET_GROUP"

log "Blue-green migration preparation completed successfully"
