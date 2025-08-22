# CivicPulse Backend - GitHub Copilot Instructions

**ALWAYS follow these instructions first and fallback to additional search and context gathering only if the information here is incomplete or found to be in error.**

CivicPulse Backend is a Django-based multi-tenant CRM/CMS platform for nonprofits, civic organizations, and political groups. It uses modern Python tooling with uv for package management, pytest for testing, and comprehensive code quality tools.

## Working Effectively

### Bootstrap Environment and Dependencies
```bash
# Install uv package manager (if not already installed)
pip install uv

# Install all dependencies - takes ~3 minutes with initial Python download
# NEVER CANCEL: Dependency installation takes 2-3 minutes. Set timeout to 300+ seconds.
uv sync

# Copy environment configuration
cp .env.example .env
```

### Database Setup and Django Commands
```bash
# Run database migrations (SQLite by default) - takes ~1 second
uv run python manage.py migrate

# Create superuser for admin access - requires no interaction
DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@example.com DJANGO_SUPERUSER_PASSWORD=admin123 uv run python manage.py createsuperuser --noinput

# Start development server - starts in ~2-3 seconds
uv run python manage.py runserver 0.0.0.0:8000
# Access at http://localhost:8000/ (redirects to admin)
# Admin at http://localhost:8000/admin/ (login: admin/admin123)
```

### Run Tests and Validation
```bash
# Run full test suite with coverage - takes ~6 seconds
# NEVER CANCEL: Test suite takes 5-10 seconds. Set timeout to 60+ seconds.
uv run pytest --cov=civicpulse --cov=cpback --cov-report=term-missing
# Expected: 138 tests pass, 80%+ coverage

# Run code quality checks - all take <10 seconds each
uv run ruff format --check .     # Format check - ~0.04 seconds
uv run ruff check .              # Linting - ~0.04 seconds  
uv run mypy civicpulse/          # Type checking - ~6 seconds
uv run bandit -r civicpulse/     # Security scan - ~0.6 seconds
```

### Docker Operations
```bash
# Use docker compose v2 (docker-compose not available)
docker compose version          # Verify availability

# Docker build currently fails due to environment issues
# Use local development setup instead of Docker for now
```

## Validation

### ALWAYS Manually Validate Changes
After making any code changes, run this complete validation sequence:

```bash
# 1. Check formatting and linting (fast - <1 second each)
uv run ruff format --check .
uv run ruff check .

# 2. Run type checking (~6 seconds)
uv run mypy civicpulse/

# 3. Run security scan (~1 second)  
uv run bandit -r civicpulse/

# 4. Run full test suite (~6 seconds)
# NEVER CANCEL: Wait for completion even if it seems slow
uv run pytest --cov=civicpulse --cov=cpback --cov-report=term-missing

# 5. Test application functionality
uv run python manage.py migrate              # Ensure migrations work
uv run python manage.py runserver &          # Start server in background
curl -f http://localhost:8000/ > /dev/null   # Test HTTP response (expect 302)
pkill -f runserver                           # Stop server
```

### End-to-End Validation Scenarios
ALWAYS test these scenarios after significant changes:

1. **Database Operations**: Run migrations, create superuser, verify admin access
2. **Authentication Flow**: Login to admin panel with created superuser
3. **Test Coverage**: Ensure all tests pass and coverage remains >80%
4. **Code Quality**: All linting, formatting, and security checks must pass

## Common Tasks

### Environment Configuration
- **Development**: Uses SQLite by default (no additional setup needed)
- **Environment file**: Copy `.env.example` to `.env` for local config
- **Database URL**: `DATABASE_URL=sqlite:///db.sqlite3` (default in .env)
- **PostgreSQL**: Available but requires manual setup of PostgreSQL server

### Development Workflow
```bash
# Start fresh development session
uv sync                                    # Install/update dependencies
uv run python manage.py migrate          # Apply any new migrations  
uv run python manage.py runserver        # Start development server

# Make changes, then validate
uv run ruff format .                      # Auto-fix formatting
uv run ruff check --fix .                # Auto-fix linting issues
uv run pytest                           # Run tests
```

### Key Project Structure
```
civicpulse-backend/
├── civicpulse/              # Main Django application
│   ├── models.py            # Core data models (User, Person, etc.)
│   ├── views.py             # Django views and API endpoints  
│   ├── forms.py             # Django forms with validation
│   ├── validators.py        # Custom validation logic
│   ├── admin.py             # Django admin interface config
│   └── tests.py             # Application-specific tests
├── cpback/                  # Django project configuration  
│   ├── settings/            # Environment-specific settings
│   │   ├── base.py          # Common settings
│   │   ├── development.py   # Development settings (default)
│   │   ├── production.py    # Production settings
│   │   └── testing.py       # Test environment settings
│   └── urls.py              # URL routing configuration
├── tests/                   # Additional test suites
├── .env.example             # Environment variables template
├── pyproject.toml           # Project dependencies and tool config
├── manage.py                # Django management script
└── docker-compose.yml       # Docker multi-service setup
```

### Frequently Modified Files
When working on authentication/user management:
- `civicpulse/models.py` - User model and related models
- `civicpulse/forms.py` - Registration, login, and profile forms
- `civicpulse/validators.py` - Password and validation logic
- `civicpulse/views.py` - Authentication views and API endpoints
- `tests/test_authentication.py` - Authentication test suite

### CI/CD Pipeline Expectations
The GitHub Actions CI (.github/workflows/ci.yml) runs:
1. Lint & Format Check (ruff)
2. Type Checking (mypy) 
3. Test Suite (pytest with PostgreSQL)
4. Security Scan (bandit)

Local validation should match CI requirements exactly.

## Common Issues and Solutions

### "Connection refused" database errors
- **Cause**: Environment trying to connect to PostgreSQL
- **Solution**: Ensure `.env` has `DATABASE_URL=sqlite:///db.sqlite3`

### Test failures after changes
- **Check**: Database migrations needed - `uv run python manage.py makemigrations`
- **Check**: Test database reset - Delete `db.sqlite3` and re-run migrations

### Docker build failures  
- **Known issue**: Docker build currently fails in this environment
- **Solution**: Use local development setup instead: `uv sync` + `uv run python manage.py runserver`

### Slow test execution
- **Normal**: First test run may be slower (~10 seconds) due to database setup
- **Optimization**: Use `pytest -n auto` for parallel execution if available

## Important Timing and Timeouts

- **Dependency installation**: 2-3 minutes (initial), 10-30 seconds (updates)
- **Test suite execution**: 5-10 seconds (138 tests)  
- **Code quality checks**: <10 seconds total for all tools
- **Django server startup**: 2-3 seconds
- **Database migrations**: <5 seconds typically

**NEVER CANCEL** any build or test command before these time limits. Set timeouts appropriately:
- `uv sync`: 300+ seconds timeout
- `pytest`: 60+ seconds timeout  
- Other commands: 30+ seconds timeout

ALWAYS wait for completion rather than canceling and retrying.