# AGENT.md — CivicPulse Backend (concise agent guide)

Purpose: give an AI coding agent the minimal, actionable repo knowledge to be productive immediately.

Quick bootstrap (minimal):
```bash
pip install uv
uv sync                    # install dependencies (set timeout >= 300s)
cp .env.example .env
uv run python manage.py migrate
```

Key commands (always use `uv run`):
- Start dev server: `uv run python manage.py runserver`
- Run tests: `uv run pytest --cov=civicpulse --cov=cpback`
- Lint/format: `uv run ruff format --check .` and `uv run ruff check .`
- Typecheck: `uv run mypy civicpulse/`
- Security scan: `uv run bandit -r civicpulse/`

Project shape & hotspots (where to look/change):
- App code: `civicpulse/` — core models and logic. Typical files: `civicpulse/models.py`, `civicpulse/views.py`, `civicpulse/forms.py`, `civicpulse/validators.py`, `civicpulse/view_modules/`.
- Settings: `cpback/settings/` — `base.py`, `development.py`, `production.py`, `testing.py`.
- Tests: top-level `tests/` and `civicpulse/tests.py`.
- Entrypoint: `manage.py`; deps in `pyproject.toml`.

Conventions and patterns (repo-specific):
- Use `uv run` as a wrapper for deterministic environment invocation. Prefer `uv run` for tests, migrations, and management commands.
- Default local DB: SQLite. Ensure `.env` contains `DATABASE_URL=sqlite:///db.sqlite3` when running locally.
- Admin/debug UI: `/admin/` (superuser can be created via env vars and `createsuperuser --noinput` in scripts).
- Views are sometimes split into `view_modules/` — prefer adding endpoints there when present to keep controllers small.

Common tasks & examples
- Add a new contact endpoint (example):
  - Model changes: `civicpulse/models.py`
  - Form/validation: `civicpulse/forms.py` and `civicpulse/validators.py`
  - Views / view module: `civicpulse/view_modules/` or `civicpulse/views/`
  - Templates: `templates/civicpulse/` (if UI changes)
  - Tests: add integration/unit tests under `tests/` or `civicpulse/tests.py`

Testing & CI expectations
- CI order: ruff -> mypy -> pytest -> bandit. Match locally before pushing.
- Use same DB strategy locally (SQLite) to reproduce CI failures quickly; CI may use Postgres so be mindful of DB-specific SQL.

Migration tips
- Run `uv run python manage.py makemigrations` then `uv run python manage.py migrate` in dev.
- If tests fail due to schema drift, delete `db.sqlite3` and re-run migrations in local dev.

Debugging hints
- Server: `uv run python manage.py runserver` and inspect logs in terminal.
- Quick smoke: after server starts, `curl -f http://localhost:8000/` should return (typically a redirect/302).

Do not change without tests
- Avoid changing settings in `cpback/settings/` or `pyproject.toml` without tests. CI checks will enforce ruff/mypy/pytest.

If you need more:
- I can extract exact CI job names, environment variables used by CI, or produce quick code examples (model/view/form/test) for common change types. Tell me which and I will add it.
