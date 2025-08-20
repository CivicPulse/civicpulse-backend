# CivicPulse Backend - Issue #2 Context
**Captured by**: John Taylor (Context Manager)  
**Date**: 2025-08-19  
**Issue**: #2 (US-006) - Secure User Authentication System  
**Version**: 1.0  

## Project Overview

### Core Information
- **Project**: CivicPulse Backend
- **Repository**: https://github.com/CivicPulse/civicpulse-backend  
- **Platform**: Multi-tenant CRM/CMS for nonprofits, civic organizations, and political groups
- **Current Issue**: #2 (US-006) - Implementing secure authentication system
- **Priority**: P0 Critical (Epic EP001: Foundation Infrastructure)

### Technology Stack
- **Backend**: Django with PostgreSQL
- **Package Manager**: uv (uv add, uv remove, uv sync)
- **Testing**: pytest with 80% coverage requirement
- **Linting**: ruff (run before all commits)
- **Type Checking**: mypy
- **Security**: bandit for security scanning
- **Logging**: Loguru for enhanced logging

## Current State

### Git Information
- **Current Branch**: feature/us-011-django-project-setup
- **Working Directory**: /home/kwhatcher/projects/civicpulse/civicpulse-backend-issue-2
- **Base Status**: Django project setup completed (US-011)
- **Next Branch**: issue/2-secure-user-authentication (to be created)

### Development Environment
- **Settings Module**: cpback.settings.development
- **Database**: SQLite (development), PostgreSQL+PostGIS (production)
- **Environment Config**: django-environ with .env file
- **Static Files**: static/ (source), staticfiles/ (collected)

## Architecture Decisions

### Django Project Structure
```
cpback/                    # Django project configuration
├── settings/
│   ├── base.py           # Common settings
│   ├── development.py    # Dev-specific settings
│   └── production.py     # Production settings
civicpulse/               # Core Django application
templates/                # HTML templates
static/                   # Static assets
media/                    # User uploads
logs/                     # Application logs
```

### Authentication Design
- **Framework**: Django's built-in authentication system
- **User Model**: Extended with role-based access control
- **Roles**: Coordinator and Field Worker roles
- **Multi-tenancy**: Schema-per-tenant approach (planned)
- **Security Features**:
  - Password validation
  - Session management
  - Account lockout protection
  - Secure password reset flow

### Code Quality Standards
- **Line Length**: 88 characters (Black default)
- **Style**: PEP 8 enforced by Ruff
- **Testing**: pytest with Django integration
- **Coverage**: Minimum 80% requirement
- **Commits**: Conventional Commits (feat:, fix:, docs:, etc.)

## Agent Coordination

### Current Agent
- **Name**: Grace Davis
- **Role**: Authentication System Implementation
- **Status**: Active on Issue #2

### Previous Work Completed
- **US-011**: Django project setup completed
- **Infrastructure**: Base Django configuration established
- **Settings**: Multi-environment settings structure implemented

### Development Workflow
1. Use uv for all Python package management
2. Run ruff linting before commits
3. Ensure pytest tests pass with 80%+ coverage
4. Work on feature branches, not main
5. Use GitHub MCP server for GitHub operations
6. Never push to GitHub unless specifically requested

## Implementation Roadmap

### Issue #2 Tasks (Current)
1. **User Model Extensions**
   - Extend Django User model for roles
   - Create coordinator/field worker role system
   - Implement role-based permissions

2. **Authentication Views**
   - Login/logout functionality
   - User registration (organization-specific)
   - Password change/reset views

3. **Security Implementation**
   - Password validation rules
   - Session security middleware
   - Account lockout protection
   - CSRF protection

4. **Templates and Forms**
   - Authentication form templates
   - User-friendly error messages
   - Responsive design for mobile

5. **Testing Suite**
   - Unit tests for authentication logic
   - Integration tests for user flows
   - Security testing for authentication
   - Achieve 80%+ test coverage

### Epic EP001 Context
- **Timeline**: Days 1-4, P0 Critical
- **Status**: 6 open issues, 1 closed
- **Foundation**: Authentication is core infrastructure requirement

## Key Environment Variables
```bash
SECRET_KEY=<django-secret-key>
DEBUG=True  # Development only
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=<postgres-connection-string>
DJANGO_SETTINGS_MODULE=cpback.settings.development
```

## Common Commands Reference
```bash
# Package management
uv add <package>
uv add --dev <package>
uv remove <package>

# Django operations  
uv run python manage.py runserver
uv run python manage.py makemigrations
uv run python manage.py migrate

# Testing and quality
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Critical Notes
- **Never commit .env files**
- **Always lint with ruff before commits**
- **Use GitHub MCP server for GitHub operations**
- **Maintain 80% test coverage minimum**
- **Follow conventional commit messages**
- **Work on feature branches only**

## Next Agent Handoff
When handing off to the next agent:
1. Review current authentication implementation progress
2. Check test coverage status
3. Verify ruff linting passes
4. Update this context with new decisions/patterns
5. Document any blockers or dependencies