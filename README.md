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

### Campaigns & Drives
Organize voter outreach with a clear hierarchy:
- **Campaigns** - The organization working to elect a candidate (e.g., "Smith for Mayor 2024")
- **Drives** - Individual voter contact efforts within a campaign (e.g., "October Phone Bank")
- **Bulk assignment** of persons filtered by party, voting likelihood, or phone availability
- **HTMX-powered interfaces** for smooth, single-page workflows
- **Concurrent user support** with row-level locking (multiple users on same drive)
- **Progress tracking** with real-time stats and completion percentage

#### Phone Banking (Drives)
- Click-to-call phone numbers with one-click dialing
- **Outcomes**: Spoke With, Will Vote, No Answer, Left Voicemail, Busy, Callback, Wrong Number, Refused

#### Door Knocking (Drives)
- **GPS-based location** to show nearby addresses sorted by walking distance
- **Interactive route map** with optimized walking path via Leaflet.js
- **OSRM route optimization** for efficient door-to-door canvassing
- **Distance indicators** showing how far each address is from current location
- **Outcomes**: Spoke at Door, Will Vote, Not Home, Left Door Hanger, Refused, No Access (Gated)

### GIS & Mapping
Full GeoDjango integration for spatial data and mapping:
- **Geocoding** - Convert addresses to coordinates (OpenCage + Nominatim fallback)
- **Interactive maps** - Leaflet.js with OpenStreetMap tiles
- **Route optimization** - OSRM-powered walking routes for door knocking
- **Spatial queries** - Radius search, district containment, proximity sorting
- **District boundaries** - Store and query voting precincts, congressional districts, etc.
- **Background geocoding** - Celery tasks for bulk address processing

### Election Tracking
Track elections and candidates for civic engagement:
- **Office management** - Define elected positions (Mayor, City Council, etc.) with jurisdiction and term info
- **Election tracking** - General, Primary, Special, and Runoff elections with comprehensive date tracking
- **Key dates** - Qualifying periods, registration deadlines, early voting, election day, certification
- **Candidate management** - Link persons as candidates with party, incumbent status, and outcome tracking
- **Campaign integration** - Associate campaigns and drives with specific elections and candidates

### Tech Stack
- **Backend**: Django 6.0+, Python 3.13+, GeoDjango
- **Frontend**: Tailwind CSS 4.1+, Flowbite components, HTMX 2.0.4, Leaflet.js
- **Database**: SpatiaLite (dev), PostGIS/PostgreSQL (prod)
- **Task Queue**: Celery with Redis
- **Package Management**: uv (Python), npm (Node)

## Quick Start

### Prerequisites

**GIS System Libraries** (required for GeoDjango):
```bash
# Ubuntu/Debian
sudo apt install gdal-bin libgdal-dev libgeos-dev libproj-dev libsqlite3-mod-spatialite

# macOS
brew install gdal geos proj spatialite-tools
```

**Redis** (required for Celery background tasks):
```bash
# Ubuntu/Debian
sudo apt install redis-server

# macOS
brew install redis
```

### Installation

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

# Start Celery worker (terminal 2) - for background geocoding
uv run celery -A example worker -l info

# Start dev server (terminal 3)
uv run python manage.py runserver
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture, data models, and development patterns.
