# CivicPulse Backend

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-4.2%2B-green.svg)](https://www.djangoproject.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Project Overview

CivicPulse is a comprehensive multi-tenant CRM/CMS platform designed specifically for nonprofits, civic organizations, and political groups. It centralizes outreach efforts, governance transparency, election tracking, volunteer coordination, and community engagement into a single, powerful platform.

## Features

### Contact Management
- **Person records** with phone numbers, emails, and addresses
- **Voter records** with party affiliation, voting history, and likelihood scores
- **CSV import** for bulk voter data loading

### Contact Campaigns
Create and manage phone banking or text campaigns with:
- **Campaign creation** with custom scripts and talking points
- **Bulk assignment** of persons filtered by party, voting likelihood, or phone availability
- **HTMX-powered calling interface** for smooth, single-page workflow
- **Concurrent caller support** with row-level locking (multiple callers on same campaign)
- **Outcome tracking**: Spoke With, No Answer, Left Voicemail, Busy, Callback, Wrong Number, Refused
- **Progress tracking** with real-time stats and completion percentage

### Tech Stack
- **Backend**: Django 4.2+, Python 3.11+
- **Frontend**: Tailwind CSS, Flowbite components, HTMX
- **Database**: SQLite (dev), PostgreSQL (prod)

## Quick Start

```bash
# Install dependencies
uv sync
npm install

# Run migrations
uv run python manage.py migrate

# Create admin user
uv run python manage.py createsuperuser

# Start Tailwind watcher (terminal 1)
npx @tailwindcss/cli -i static/src/input.css -o static/src/output.css --watch

# Start dev server (terminal 2)
uv run python manage.py runserver
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture, data models, and development patterns.
