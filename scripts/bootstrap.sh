#!/usr/bin/env bash
#
# CivicPulse Backend Bootstrap Script
# ====================================
# One-command setup for a working CivicPulse installation
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/CivicPulse/civicpulse-backend/main/scripts/bootstrap.sh | bash
#   # or
#   wget -qO- https://raw.githubusercontent.com/CivicPulse/civicpulse-backend/main/scripts/bootstrap.sh | bash
#
# Prerequisites:
#   - Redis running on localhost:6379
#   - PostgreSQL database accessible
#   - Git installed
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

REPO_URL="https://github.com/CivicPulse/civicpulse-backend.git"
INSTALL_DIR="${CIVICPULSE_INSTALL_DIR:-$HOME/civicpulse-backend}"
PYTHON_MIN_VERSION="3.13"
BRANCH="${CIVICPULSE_BRANCH:-main}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    echo "  _____ _       _      _____       _           "
    echo " / ____(_)     (_)    |  __ \\     | |          "
    echo "| |     ___   ___  ___| |__) |   _| |___  ___  "
    echo "| |    | \\ \\ / / |/ __| ___/ | | | / __|/ _ \\ "
    echo "| |____| |\\ V /| | (__| |   | |_| | \\__ \\  __/ "
    echo " \\_____|_| \\_/ |_|\\___|_|    \\__,_|_|___/\\___| "
    echo -e "${NC}"
    echo -e "${BOLD}Backend Bootstrap Script${NC}"
    echo "=========================================="
    echo ""
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

prompt_input() {
    local prompt="$1"
    local default="${2:-}"
    local var_name="$3"
    local is_secret="${4:-false}"

    if [ -n "$default" ]; then
        prompt="$prompt [$default]"
    fi

    echo -en "${CYAN}$prompt: ${NC}"

    if [ "$is_secret" = "true" ]; then
        read -rs response
        echo ""
    else
        read -r response
    fi

    if [ -z "$response" ] && [ -n "$default" ]; then
        response="$default"
    fi

    eval "$var_name=\"\$response\""
}

prompt_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    local response

    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]"
    else
        prompt="$prompt [y/N]"
    fi

    echo -en "${CYAN}$prompt: ${NC}"
    read -r response

    response="${response:-$default}"
    response=$(echo "$response" | tr '[:upper:]' '[:lower:]')

    [ "$response" = "y" ] || [ "$response" = "yes" ]
}

generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
    openssl rand -base64 50 | tr -d '/+=' | cut -c1-50 || \
    head -c 50 /dev/urandom | base64 | tr -d '/+=' | cut -c1-50
}

check_command() {
    command -v "$1" &> /dev/null
}

# =============================================================================
# Prerequisite Checks
# =============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."

    local errors=0

    # Check for git
    if ! check_command git; then
        log_error "Git is not installed. Please install git first."
        errors=$((errors + 1))
    else
        log_success "Git found: $(git --version)"
    fi

    # Check for Python 3.13+
    if check_command python3; then
        local python_version
        python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 13) else 1)" 2>/dev/null; then
            log_success "Python found: $python_version"
        else
            log_warn "Python $python_version found, but Python 3.13+ is recommended"
            log_warn "The application may still work but some features might be limited"
        fi
    else
        log_error "Python 3 is not installed. Please install Python 3.13+."
        errors=$((errors + 1))
    fi

    # Check for Redis
    log_info "Checking Redis connection..."
    if check_command redis-cli; then
        if redis-cli ping &>/dev/null; then
            log_success "Redis is running on localhost"
        else
            log_error "Redis is not responding. Please ensure Redis is running on localhost:6379"
            errors=$((errors + 1))
        fi
    else
        log_warn "redis-cli not found. Cannot verify Redis connection."
        log_warn "Please ensure Redis is running on localhost:6379"
    fi

    # Check for curl or wget
    if ! check_command curl && ! check_command wget; then
        log_error "Neither curl nor wget found. Please install one of them."
        errors=$((errors + 1))
    fi

    if [ $errors -gt 0 ]; then
        log_error "Prerequisites check failed with $errors error(s)"
        exit 1
    fi

    echo ""
}

# =============================================================================
# UV Package Manager Installation
# =============================================================================

install_uv() {
    if check_command uv; then
        log_success "uv is already installed: $(uv --version)"
        return 0
    fi

    log_info "Installing uv package manager..."

    if check_command curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif check_command wget; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    fi

    # Add uv to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    export PATH="$HOME/.cargo/bin:$PATH"

    if check_command uv; then
        log_success "uv installed successfully: $(uv --version)"
    else
        log_error "Failed to install uv. Please install it manually: https://docs.astral.sh/uv/"
        exit 1
    fi
}

# =============================================================================
# Configuration Collection
# =============================================================================

collect_configuration() {
    echo ""
    echo -e "${BOLD}Configuration Setup${NC}"
    echo "===================="
    echo "Please provide the following configuration values."
    echo "Press Enter to accept default values shown in brackets."
    echo ""

    # Database Configuration
    echo -e "${BOLD}Database Configuration:${NC}"
    echo "Format: postgresql://user:password@host:port/database"
    echo "Example: postgresql://civicpulse:mypassword@localhost:5432/civicpulse_db"
    echo ""
    prompt_input "Database URL" "postgresql://civicpulse:civicpulse@localhost:5432/civicpulse_db" DATABASE_URL
    echo ""

    # Redis Configuration
    echo -e "${BOLD}Redis Configuration:${NC}"
    prompt_input "Redis URL" "redis://localhost:6379/0" REDIS_URL
    echo ""

    # Application Configuration
    echo -e "${BOLD}Application Configuration:${NC}"
    prompt_input "Site Name" "CivicPulse" SITE_NAME
    prompt_input "Site URL" "http://localhost:8000" SITE_URL
    prompt_input "Allowed Hosts (comma-separated)" "localhost,127.0.0.1,0.0.0.0" ALLOWED_HOSTS
    echo ""

    # Environment Type
    echo -e "${BOLD}Environment Type:${NC}"
    echo "1) Development (DEBUG=True, console email)"
    echo "2) Production (DEBUG=False, SMTP email, SSL enabled)"
    prompt_input "Select environment" "1" ENV_TYPE

    if [ "$ENV_TYPE" = "2" ]; then
        IS_PRODUCTION=true
        DEBUG="False"
        DJANGO_SETTINGS_MODULE="cpback.settings.production"

        echo ""
        echo -e "${BOLD}Production Settings:${NC}"
        prompt_input "Enable SSL redirect" "true" SECURE_SSL_REDIRECT

        echo ""
        echo -e "${BOLD}Email Configuration (for password resets, notifications):${NC}"
        prompt_input "SMTP Host" "smtp.gmail.com" EMAIL_HOST
        prompt_input "SMTP Port" "587" EMAIL_PORT
        prompt_input "SMTP Username" "" EMAIL_HOST_USER
        prompt_input "SMTP Password" "" EMAIL_HOST_PASSWORD true
        prompt_input "From Email" "noreply@civicpulse.com" DEFAULT_FROM_EMAIL
    else
        IS_PRODUCTION=false
        DEBUG="True"
        DJANGO_SETTINGS_MODULE="cpback.settings.development"
        SECURE_SSL_REDIRECT="False"
        EMAIL_HOST=""
        EMAIL_PORT="587"
        EMAIL_HOST_USER=""
        EMAIL_HOST_PASSWORD=""
        DEFAULT_FROM_EMAIL=""
    fi
    echo ""

    # Admin User
    echo -e "${BOLD}Admin User Setup:${NC}"
    prompt_input "Admin username" "admin" ADMIN_USERNAME
    prompt_input "Admin email" "admin@localhost" ADMIN_EMAIL
    prompt_input "Admin password" "" ADMIN_PASSWORD true

    if [ -z "$ADMIN_PASSWORD" ]; then
        ADMIN_PASSWORD=$(generate_secret_key | cut -c1-16)
        echo -e "${YELLOW}Generated admin password: $ADMIN_PASSWORD${NC}"
        echo -e "${YELLOW}Please save this password securely!${NC}"
    fi
    echo ""

    # Generate secret key
    SECRET_KEY=$(generate_secret_key)
    log_info "Generated Django SECRET_KEY"

    # Confirm configuration
    echo ""
    echo -e "${BOLD}Configuration Summary:${NC}"
    echo "========================"
    echo "Install Directory: $INSTALL_DIR"
    echo "Environment: $([ "$IS_PRODUCTION" = true ] && echo 'Production' || echo 'Development')"
    echo "Database URL: ${DATABASE_URL//:*@/:***@}"  # Mask password
    echo "Redis URL: $REDIS_URL"
    echo "Site Name: $SITE_NAME"
    echo "Site URL: $SITE_URL"
    echo "Admin User: $ADMIN_USERNAME"
    echo ""

    if ! prompt_yes_no "Proceed with installation?" "y"; then
        log_info "Installation cancelled by user"
        exit 0
    fi
    echo ""
}

# =============================================================================
# Installation Steps
# =============================================================================

clone_repository() {
    log_info "Cloning repository..."

    if [ -d "$INSTALL_DIR" ]; then
        if [ -d "$INSTALL_DIR/.git" ]; then
            log_warn "Directory $INSTALL_DIR already exists"
            if prompt_yes_no "Update existing installation?" "y"; then
                cd "$INSTALL_DIR"
                git fetch origin
                git checkout "$BRANCH"
                git pull origin "$BRANCH"
                log_success "Repository updated"
                return 0
            else
                log_error "Installation cancelled. Remove $INSTALL_DIR or choose a different location."
                exit 1
            fi
        else
            log_error "Directory $INSTALL_DIR exists but is not a git repository"
            exit 1
        fi
    fi

    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    log_success "Repository cloned to $INSTALL_DIR"
}

create_env_file() {
    log_info "Creating .env configuration file..."

    local env_file="$INSTALL_DIR/.env"

    cat > "$env_file" << EOF
# CivicPulse Configuration
# Generated by bootstrap script on $(date)

# Django Settings
SECRET_KEY=$SECRET_KEY
DEBUG=$DEBUG
ALLOWED_HOSTS=$ALLOWED_HOSTS
DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

# Database Configuration
DATABASE_URL=$DATABASE_URL

# Redis Configuration
REDIS_URL=$REDIS_URL
CELERY_BROKER_URL=$REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_URL

# Cache Configuration
CACHE_KEY_PREFIX=civicpulse_$([ "$IS_PRODUCTION" = true ] && echo 'prod' || echo 'dev')

# Django-Axes Whitelist IPs
AXES_WHITELIST_IPS=127.0.0.1,::1

# Static and Media Files
STATIC_ROOT=staticfiles
MEDIA_ROOT=media

# Application Settings
SITE_NAME=$SITE_NAME
SITE_URL=$SITE_URL
API_THROTTLE_RATE=1000/hour

# File Upload Settings
PERSON_IMPORT_MAX_FILE_SIZE=10485760

# Security Monitoring Thresholds
SECURITY_FAILED_LOGIN_THRESHOLD=5
SECURITY_FAILED_LOGIN_WINDOW_HOURS=1
SECURITY_EXPORT_THRESHOLD=10
SECURITY_EXPORT_WINDOW_HOURS=24
SECURITY_PRIVILEGE_ESCALATION_WINDOW_HOURS=24

# Logging
LOG_LEVEL=$([ "$IS_PRODUCTION" = true ] && echo 'WARNING' || echo 'DEBUG')
DJANGO_LOG_LEVEL=$([ "$IS_PRODUCTION" = true ] && echo 'WARNING' || echo 'INFO')
EOF

    # Add production-specific settings
    if [ "$IS_PRODUCTION" = true ]; then
        cat >> "$env_file" << EOF

# Security Settings (Production)
SECURE_SSL_REDIRECT=$SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=$EMAIL_HOST
EMAIL_PORT=$EMAIL_PORT
EMAIL_HOST_USER=$EMAIL_HOST_USER
EMAIL_HOST_PASSWORD=$EMAIL_HOST_PASSWORD
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=$DEFAULT_FROM_EMAIL
EOF
    else
        cat >> "$env_file" << EOF

# Development Settings
SECURE_SSL_REDIRECT=False
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EOF
    fi

    chmod 600 "$env_file"
    log_success "Configuration file created: $env_file"
}

install_dependencies() {
    log_info "Installing Python dependencies..."

    cd "$INSTALL_DIR"

    # Sync dependencies with uv
    uv sync

    log_success "Dependencies installed"
}

setup_database() {
    log_info "Setting up database..."

    cd "$INSTALL_DIR"

    # Run migrations
    log_info "Running database migrations..."
    uv run python manage.py migrate --noinput

    log_success "Database migrations complete"
}

create_admin_user() {
    log_info "Creating admin user..."

    cd "$INSTALL_DIR"

    # Create superuser using Django shell
    uv run python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$ADMIN_USERNAME').exists():
    User.objects.create_superuser('$ADMIN_USERNAME', '$ADMIN_EMAIL', '$ADMIN_PASSWORD')
    print('Admin user created successfully')
else:
    print('Admin user already exists')
EOF

    log_success "Admin user configured"
}

collect_static_files() {
    log_info "Collecting static files..."

    cd "$INSTALL_DIR"

    uv run python manage.py collectstatic --noinput

    log_success "Static files collected"
}

setup_production_cache() {
    if [ "$IS_PRODUCTION" = true ]; then
        log_info "Setting up production cache..."

        cd "$INSTALL_DIR"

        uv run python manage.py setup_production --create-cache-table || true

        log_success "Production cache configured"
    fi
}

verify_installation() {
    log_info "Verifying installation..."

    cd "$INSTALL_DIR"

    # Run Django system check
    if uv run python manage.py check; then
        log_success "Django system check passed"
    else
        log_warn "Django system check reported issues (non-fatal)"
    fi

    # Test Redis connection
    if uv run python -c "import redis; r = redis.from_url('$REDIS_URL'); r.ping(); print('Redis OK')"; then
        log_success "Redis connection verified"
    else
        log_warn "Redis connection failed - application will use database cache fallback"
    fi

    # Test database connection
    if uv run python manage.py dbshell -- -c "SELECT 1;" &>/dev/null; then
        log_success "Database connection verified"
    else
        log_warn "Could not verify database connection via dbshell"
    fi
}

print_completion_message() {
    echo ""
    echo -e "${GREEN}=============================================${NC}"
    echo -e "${GREEN}    CivicPulse Installation Complete!${NC}"
    echo -e "${GREEN}=============================================${NC}"
    echo ""
    echo -e "${BOLD}Installation Directory:${NC} $INSTALL_DIR"
    echo ""
    echo -e "${BOLD}Quick Start Commands:${NC}"
    echo "  cd $INSTALL_DIR"
    echo ""
    echo "  # Start the development server"
    echo "  uv run python manage.py runserver"
    echo ""
    echo "  # Or bind to all interfaces (for remote access)"
    echo "  uv run python manage.py runserver 0.0.0.0:8000"
    echo ""
    echo -e "${BOLD}Access Points:${NC}"
    echo "  Application: $SITE_URL"
    echo "  Admin Panel: $SITE_URL/admin"
    echo ""
    echo -e "${BOLD}Admin Credentials:${NC}"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Email: $ADMIN_EMAIL"
    if [ -n "${ADMIN_PASSWORD:-}" ]; then
        echo -e "  Password: ${YELLOW}(as configured during setup)${NC}"
    fi
    echo ""
    echo -e "${BOLD}Useful Commands:${NC}"
    echo "  # Run tests"
    echo "  uv run pytest"
    echo ""
    echo "  # Create a new migration"
    echo "  uv run python manage.py makemigrations"
    echo ""
    echo "  # Run code linting"
    echo "  uv run ruff check ."
    echo ""
    echo "  # Format code"
    echo "  uv run ruff format ."
    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  Environment file: $INSTALL_DIR/.env"
    echo "  Settings module: $DJANGO_SETTINGS_MODULE"
    echo ""

    if [ "$IS_PRODUCTION" = true ]; then
        echo -e "${YELLOW}Production Notes:${NC}"
        echo "  - Configure a reverse proxy (nginx/caddy) for production use"
        echo "  - Set up SSL certificates for HTTPS"
        echo "  - Consider using gunicorn or uvicorn for production deployment"
        echo "  - Example: uv run gunicorn cpback.wsgi:application --bind 0.0.0.0:8000"
        echo ""
    fi

    echo -e "${CYAN}Thank you for using CivicPulse!${NC}"
    echo ""
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_banner

    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --branch)
                BRANCH="$2"
                shift 2
                ;;
            --non-interactive)
                NON_INTERACTIVE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --install-dir DIR    Installation directory (default: ~/civicpulse-backend)"
                echo "  --branch BRANCH      Git branch to checkout (default: main)"
                echo "  --non-interactive    Skip interactive prompts (use defaults/env vars)"
                echo "  --help, -h           Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  CIVICPULSE_INSTALL_DIR    Installation directory"
                echo "  CIVICPULSE_BRANCH         Git branch to use"
                echo "  DATABASE_URL              PostgreSQL connection string"
                echo "  REDIS_URL                 Redis connection string"
                echo ""
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    check_prerequisites
    install_uv
    collect_configuration
    clone_repository
    create_env_file
    install_dependencies
    setup_database
    create_admin_user
    collect_static_files
    setup_production_cache
    verify_installation
    print_completion_message
}

# Run main function
main "$@"
