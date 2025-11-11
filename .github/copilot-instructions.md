# CivicPulse Backend - GitHub Copilot Instructions

**ALWAYS follow these instructions first and fallback to additional search and context gathering only if the information here is incomplete or found to be in error.**

CivicPulse Backend is a Django-based multi-tenant CRM/CMS platform for nonprofits, civic organizations, and political groups. It uses modern Python tooling with uv for package management, pytest for testing, and comprehensive code quality tools.

## Working Effectively
```markdown
# CivicPulse Backend — Copilot instructions (concise)

Follow this file first. It captures the minimal, project-specific commands and patterns to be productive.

1) Quick bootstrap
```bash
pip install uv
uv sync                  # install dependencies (set timeout >= 300s)
cp .env.example .env
uv run python manage.py migrate
```

2) Common dev/test commands (use `uv run` prefix)
- Run server: `uv run python manage.py runserver` (admin at `/admin`)
- Tests: `uv run pytest --cov=civicpulse --cov=cpback`
- Lint/format: `uv run ruff format --check .` and `uv run ruff check .`
- Typecheck: `uv run mypy civicpulse/`
- Security scan: `uv run bandit -r civicpulse/`

3) Project shape & hotspots (look here for behaviour to change)
- App code: `civicpulse/` (models: `civicpulse/models.py`, views: `civicpulse/views.py`, forms: `civicpulse/forms.py`)
- Project settings: `cpback/settings/` (development/testing/production)
- Tests: `tests/` and `civicpulse/tests.py` (authentication, persons, forms)
- Entrypoint: `manage.py`, deps in `pyproject.toml`

4) Conventions & patterns to follow
- Uses `uv` wrapper for deterministic commands — always run via `uv run` when invoking tools/test.
- Default DB is SQLite for local dev (`DATABASE_URL=sqlite:///db.sqlite3` in `.env`). CI may run PostgreSQL.
- Admin and debug-friendly views are in `civicpulse/views/` or `civicpulse/view_modules/` — prefer existing view modules when adding endpoints.

5) CI expectations
- CI runs ruff -> mypy -> pytest -> bandit. Match these locally before pushing.

6) Troubleshooting notes (discoverable rules)
- If tests try to reach Postgres locally, set `.env` to SQLite as above.
- Docker builds are known to be flaky locally; prefer local `uv sync` + `uv run` flow.

If anything in this file is unclear or you'd like more examples (specific tests to run, common code patterns to change), tell me which area to expand and I'll update it.
```