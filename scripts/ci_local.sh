#!/bin/bash
# CI Local Runner - Run CI checks locally before pushing
# This script mimics the GitHub Actions CI pipeline

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Header
echo "=================================================="
echo "       CivicPulse CI Pipeline - Local Runner     "
echo "=================================================="
echo ""

# Track overall status
FAILED_CHECKS=()

# 1. Environment Check
log_info "Checking environment..."
if ! command -v uv &> /dev/null; then
    log_error "UV is not installed. Please install it first."
    exit 1
fi

if ! command -v python &> /dev/null; then
    log_error "Python is not installed."
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
if [[ ! "$PYTHON_VERSION" == "3.13" ]] && [[ ! "$PYTHON_VERSION" == "3.12" ]] && [[ ! "$PYTHON_VERSION" == "3.11" ]]; then
    log_warning "Python version $PYTHON_VERSION detected. CI uses Python 3.13"
fi

log_success "Environment check passed"
echo ""

# 2. Dependency Installation
log_info "Installing dependencies..."
uv sync --frozen || {
    log_error "Failed to install dependencies"
    FAILED_CHECKS+=("dependencies")
}
echo ""

# 3. Code Formatting Check
log_info "Running code formatting check (Ruff)..."
if uv run ruff format --check . ; then
    log_success "Code formatting check passed"
else
    log_warning "Code formatting issues found. Run 'uv run ruff format .' to fix"
    FAILED_CHECKS+=("formatting")
fi
echo ""

# 4. Linting Check
log_info "Running linting check (Ruff)..."
if uv run ruff check . ; then
    log_success "Linting check passed"
else
    log_warning "Linting issues found. Run 'uv run ruff check --fix .' to fix some issues"
    FAILED_CHECKS+=("linting")
fi
echo ""

# 5. Type Checking
log_info "Running type checking (mypy)..."
export SECRET_KEY="dummy-secret-key-for-ci"
if uv run mypy civicpulse/ ; then
    log_success "Type checking passed"
else
    log_warning "Type checking issues found"
    FAILED_CHECKS+=("type-checking")
fi
echo ""

# 6. Security Scan
log_info "Running security scan (Bandit)..."
if uv run bandit -r civicpulse/ -ll ; then
    log_success "Security scan passed"
else
    log_warning "Security issues found"
    FAILED_CHECKS+=("security")
fi
echo ""

# 7. Dependency Audit
log_info "Running dependency vulnerability check (pip-audit)..."
if uv run pip-audit ; then
    log_success "No known vulnerabilities in dependencies"
else
    log_warning "Vulnerable dependencies found"
    FAILED_CHECKS+=("dependencies-audit")
fi
echo ""

# 8. Tests with Coverage
log_info "Running tests with coverage..."
export DJANGO_SETTINGS_MODULE=cpback.settings.testing
export DATABASE_URL="sqlite:///:memory:"
export SECRET_KEY="test-secret-key"

if uv run pytest --cov=civicpulse --cov-report=term-missing --cov-fail-under=80 ; then
    log_success "Tests passed with sufficient coverage"
else
    log_error "Tests failed or coverage below 80%"
    FAILED_CHECKS+=("tests")
fi
echo ""

# 9. Django Checks
log_info "Running Django system checks..."
if uv run python manage.py check --deploy --fail-level WARNING 2>/dev/null ; then
    log_success "Django checks passed"
else
    log_warning "Django deployment checks found issues"
    FAILED_CHECKS+=("django-checks")
fi
echo ""

# 10. Migration Check
log_info "Checking for missing migrations..."
if uv run python manage.py makemigrations --check --dry-run ; then
    log_success "No missing migrations"
else
    log_warning "Missing migrations detected. Run 'uv run python manage.py makemigrations'"
    FAILED_CHECKS+=("migrations")
fi
echo ""

# Summary
echo "=================================================="
echo "                    SUMMARY                      "
echo "=================================================="

if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
    log_success "✅ All CI checks passed! Ready to push."
    echo ""
    echo "You can now push your changes:"
    echo "  git push origin $(git branch --show-current)"
    exit 0
else
    log_error "❌ Some checks failed:"
    for check in "${FAILED_CHECKS[@]}"; do
        echo "  - $check"
    done
    echo ""
    echo "Please fix the issues before pushing."
    echo "Run this script again after making fixes."
    exit 1
fi