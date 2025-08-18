# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Information
- Owner: CivicPulse - https://github.com/CivicPulse/civicpulse-backend
- Project: Multi-tenant CRM/CMS platform for nonprofits, civic organizations, and political groups

## Common Development Commands

### Package Management
```bash
# Add dependencies
uv add <package-name>
uv add --dev <package-name>  # For development dependencies

# Remove packages
uv remove <package-name>

# Install all dependencies
uv sync
```

### Django Commands
```bash
# Run development server
uv run python manage.py runserver

# Database migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Run Django shell
uv run python manage.py shell

# Collect static files
uv run python manage.py collectstatic
```

### Testing
```bash
# Run all tests with coverage
uv run pytest

# Run specific test module
uv run pytest tests/test_members.py

# Run tests with parallel execution
uv run pytest -n auto

# Run tests with verbose output
uv run pytest -v
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .
uv run ruff check --fix .  # Auto-fix issues

# Type checking
uv run mypy civicpulse/

# Security scan
uv run bandit -r civicpulse/
```

## Project Architecture

### Django Settings Structure
- `cpback/settings/base.py` - Common settings for all environments
- `cpback/settings/development.py` - Development-specific settings
- `cpback/settings/production.py` - Production-specific settings
- Settings module is set via `DJANGO_SETTINGS_MODULE` environment variable

### Key Application Components
- **Main App**: `civicpulse/` - Core Django application
- **Settings**: `cpback/` - Django project configuration
- **Templates**: `templates/` - Django HTML templates
- **Static Files**: `static/` (source), `staticfiles/` (collected)
- **Media Files**: `media/` - User-uploaded content
- **Logs**: `logs/` - Application logs

### Environment Configuration
- Uses `django-environ` for environment variable management
- `.env` file for local development (not committed)
- `.env.example` as template for environment variables
- Key variables: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`

### Database
- Default: SQLite for development
- Production: PostgreSQL with PostGIS (configured via `DATABASE_URL`)
- Multi-tenant architecture planned (schema-per-tenant approach)

### Testing Configuration
- Framework: pytest with Django integration
- Coverage requirement: 80% minimum
- Test settings: `DJANGO_SETTINGS_MODULE=cpback.settings.development`
- Coverage reports: HTML and terminal output

### Development Workflow
1. Always use `uv` for Python package management
2. Run `ruff` for linting before commits
3. Ensure tests pass with 80%+ coverage
4. Use conventional commits (feat:, fix:, docs:, etc.)
5. Work on feature branches, not main

## Important Patterns and Conventions

### Code Style
- Python: PEP 8 enforced by Ruff
- Line length: 88 characters (Black default)
- Django-specific linting rules enabled
- Type hints encouraged (mypy configured)

### Security Considerations
- Never commit `.env` files
- Use environment variables for sensitive data
- Bandit configured for security scanning
- Django security middleware enabled

### Logging
- Loguru integration for enhanced logging
- Separate log files for errors and general logs
- Rotating file handlers to manage disk space
- Structured logging with verbose formatting

## Future Architecture (From README)
- Modular monolith design with plugin-like Django apps
- API-first development with Django REST Framework
- WebSocket support via Django Channels
- Task queue with Celery and Redis
- CMS integration with Wagtail (headless mode)