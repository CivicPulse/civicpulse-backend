#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting CivicPulse Backend...${NC}"

# Function to wait for database
wait_for_db() {
    echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
    
    # Extract database info from DATABASE_URL if available
    if [ -n "$DATABASE_URL" ]; then
        # Wait for database connection using Python
        python << END
import os
import time
import psycopg2
from urllib.parse import urlparse

database_url = os.getenv('DATABASE_URL')
if database_url:
    url = urlparse(database_url)
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host=url.hostname,
                port=url.port or 5432,
                user=url.username,
                password=url.password,
                database=url.path[1:]  # Remove leading slash
            )
            conn.close()
            print("✅ Database is ready!")
            break
        except psycopg2.OperationalError:
            retry_count += 1
            print(f"⏳ Database not ready, retrying... ({retry_count}/{max_retries})")
            time.sleep(2)
    else:
        print("❌ Database connection failed after maximum retries")
        exit(1)
END
    else
        echo "ℹ️  No DATABASE_URL found, skipping database wait"
    fi
}

# Function to run database migrations
run_migrations() {
    echo -e "${YELLOW}🔄 Running database migrations...${NC}"
    python manage.py migrate --noinput
    echo -e "${GREEN}✅ Migrations completed${NC}"
}

# Function to collect static files
collect_static() {
    echo -e "${YELLOW}📦 Collecting static files...${NC}"
    python manage.py collectstatic --noinput --clear
    echo -e "${GREEN}✅ Static files collected${NC}"
}

# Function to create superuser if needed
create_superuser() {
    if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ] && [ "$DJANGO_SUPERUSER_EMAIL" ]; then
        echo -e "${YELLOW}👤 Creating superuser...${NC}"
        python manage.py createsuperuser --noinput || echo "ℹ️  Superuser already exists"
        echo -e "${GREEN}✅ Superuser setup completed${NC}"
    else
        echo "ℹ️  Skipping superuser creation (missing environment variables)"
    fi
}

# Function to start the application
start_app() {
    echo -e "${GREEN}🌟 Starting application server...${NC}"
    
    # Check if gunicorn is available, otherwise fall back to runserver
    if command -v gunicorn &> /dev/null; then
        echo "🚀 Starting with Gunicorn (Production)"
        exec gunicorn cpback.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers ${GUNICORN_WORKERS:-3} \
            --worker-class gthread \
            --threads ${GUNICORN_THREADS:-2} \
            --worker-connections ${GUNICORN_WORKER_CONNECTIONS:-1000} \
            --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
            --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
            --timeout ${GUNICORN_TIMEOUT:-30} \
            --keep-alive ${GUNICORN_KEEPALIVE:-5} \
            --log-level ${GUNICORN_LOG_LEVEL:-info} \
            --access-logfile - \
            --error-logfile - \
            --capture-output
    else
        echo "⚠️  Gunicorn not found, falling back to development server"
        exec python manage.py runserver 0.0.0.0:8000
    fi
}

# Main execution flow
case "$1" in
    "celery")
        echo -e "${GREEN}🔄 Starting Celery Worker...${NC}"
        wait_for_db
        exec celery -A cpback worker --loglevel=info
        ;;
    "celery-beat")
        echo -e "${GREEN}⏰ Starting Celery Beat...${NC}"
        wait_for_db
        exec celery -A cpback beat --loglevel=info
        ;;
    "migrate")
        wait_for_db
        run_migrations
        ;;
    "collectstatic")
        collect_static
        ;;
    "createsuperuser")
        wait_for_db
        create_superuser
        ;;
    "bash")
        exec /bin/bash
        ;;
    *)
        # Default: Full application startup
        wait_for_db
        run_migrations
        collect_static
        create_superuser
        start_app
        ;;
esac