# CivicPulse Backend

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-6.0%2B-green.svg)](https://www.djangoproject.com/)
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

### Election Tracking
Track elections and candidates for civic engagement:
- **Office management** - Define elected positions (Mayor, City Council, etc.) with jurisdiction and term info
- **Election tracking** - General, Primary, Special, and Runoff elections with comprehensive date tracking
- **Key dates** - Qualifying periods, registration deadlines, early voting, election day, certification
- **Candidate management** - Link persons as candidates with party, incumbent status, and outcome tracking
- **Campaign integration** - Associate contact campaigns with specific elections and candidates

### Tech Stack
- **Backend**: Django 6.0+, Python 3.13+
- **Frontend**: Tailwind CSS 4.1+, Flowbite components, HTMX 2.0.4
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Package Management**: uv (Python), npm (Node)

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
