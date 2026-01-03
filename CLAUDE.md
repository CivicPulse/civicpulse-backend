# CLAUDE.md

CivicPulse: Django civic engagement platform for voter contact, election tracking, and multi-channel outreach.

**Stack:** Django 6.0+, Python 3.13+, GeoDjango, Tailwind 4.1+, HTMX 2.0.4, Leaflet.js, SpatiaLite/PostGIS, Celery+Redis, uv, npm

**Always:** Use `uv` for Python, Context7 MCP for docs, Conventional Commits. Update docs when changing functionality.

## Quick Reference

**Common Commands:**
```bash
uv sync                                    # Install dependencies
uv run python manage.py runserver          # Start dev server
uv run python manage.py migrate            # Run migrations
uv run celery -A example worker -l info    # Start Celery worker
npx @tailwindcss/cli -i static/src/input.css -o static/src/output.css --watch
```

**Key Terminology:**
- **Campaign** (model: `Campaign`) - Organization to elect candidate/advance issue
- **Drive** (model: `ContactEffort`) - Specific outreach effort (phone bank, canvass)
- **Race** (model: `Election`) - Election for specific office

**Project Structure:** `src/civicpulse/` (models, views, forms, admin, tasks, services/, templates/)

## Architecture

**Frontend:** Tailwind CSS + django-compressor, Flowbite (CDN), HTMX 2.0.4, Leaflet.js (CDN)
**Auth:** Django built-in, `@login_required` on all views, admin-only user creation
**Database:** SpatiaLite (dev), PostGIS (prod), UUID PKs, SRID 4326 (WGS84)
**GIS:** GeoDjango, PointField (locations), MultiPolygonField (boundaries), spatial queries
**Tasks:** Celery + Redis, geocoding with rate limiting, batch processing

## Core Data Models

### Person (`models.py:7-53`)
Contact record. Fields: `first_name`, `last_name`, `middle_name`, `nickname`, `organization`, `job_title`, `voter_id` (unique), `user` (OneToOne → User, optional)
Relations: `phone_numbers`, `emails`, `addresses`, `voter_record` (OneToOne), `contact_attempts`, `effort_assignments`

### VoterRecord (`models.py`)
OneToOne with Person. Demographics: `registered_party`, `gender`, `age`, `ethnicity`, `marital_status`, `spoken_language`
Location: `location` (PointField, SRID 4326), `latitude`/`longitude` (legacy)
Voting: `likelihood_general/primary/combined` (strings), `voted_general/primary_2024/2022/2020/2018` (bools)

### Office (`models.py:197-240`)
Elected position. Fields: `name`, `level` (federal/state/county/city/school_district/other), `city`, `county`, `state`, `term_length_years`, `description`

### Election (`models.py:243-305`)
Race for office. Fields: `office` (FK), `election_type` (general/primary/special/runoff), `year`, `parent_election` (FK self), `status` (upcoming/active/completed/certified)
Dates: `qualifying_start/end`, `registration_deadline`, `absentee_request_deadline`, `early_voting_start/end`, `election_day`, `certification_date`

### Candidate (`models.py:339-377`)
Links Person to Election. Fields: `person` (FK Person, **SET_NULL**, nullable), `election` (FK), `party_affiliation`, `is_incumbent`, `status` (active/withdrawn/won/lost), `campaign_website`, `campaign_slogan`
Note: `SET_NULL` preserves candidate if person deleted. Views handle `person=None` gracefully.

### Campaign (`models.py`)
Organization umbrella. Fields: `name`, `description`, `candidate` (FK, optional), `election` (FK, optional), `is_active`, `created_by`, `created_at`, `updated_at`
Design: Optional fields allow issue-based campaigns, multiple campaigns per candidate

### ContactEffort (`models.py`) - "Drive"
Outreach effort. Fields: `name`, `description`, `script`, `is_active`, `campaign` (FK Campaign, SET_NULL, optional), `election` (FK, optional), `candidate` (FK, optional), `created_by`

### EffortAssignment (`models.py`)
Pre-assigns targets with locking. **Dual-target polymorphism:**
- `person` (FK Person, nullable) - For non-election drives
- `election_voter` (FK ElectionVoter, nullable) - For election-based drives
- `status`: pending → in_progress → completed
- `locked_by`/`locked_at`: Prevents concurrent access (10-min timeout)
Constraints: `unique_person_assignment`, `unique_election_voter_assignment`, `assignment_must_have_target`

### ContactAttempt (`models.py:443-510`)
Logs contact. **Dual-target polymorphism** like EffortAssignment.
`contact_type`: call/text/door_knock
Outcomes (terminal in bold): no_answer, busy, left_voicemail, callback_requested, **wrong_number**, **spoke_with**, **will_vote**, **refused**, not_home, left_door_hanger, **spoke_at_door**, **refused_door**, no_access

### District (`models.py`)
Geographic boundaries. Fields: `name`, `district_type` (precinct/congressional/state_house/state_senate/county/city), `identifier`, `state`, `county`, `boundary` (MultiPolygonField, SRID 4326), `source`, `effective_date`

## Key URL Patterns

```
/campaigns/                    # Campaign CRUD (org_campaign_*)
/drives/                       # Drive CRUD (campaign_*)
/drives/<uuid>/call/           # Phone banking session
/drives/<uuid>/knock/          # Door knocking session
/offices/                      # Office CRUD
/elections/                    # Election CRUD
/candidates/<uuid>/            # Candidate detail
/api/drives/<uuid>/locations/  # GeoJSON locations
/api/drives/<uuid>/route/      # Optimized route
```

## Critical View Helpers (`views.py`)

**`get_next_assignment(effort, user)`** (lines 673-701)
Row-level locking with `select_for_update(skip_locked=True)`. Releases stale locks (>10 min). Returns locked assignment or None.

**`get_assignment_target_with_details(assignment, effort)`**
Handles dual-target polymorphism. Returns `(target, target_type)` where `target_type` is `"person"` or `"election_voter"`. Returns `(None, None)` if orphaned.

**`get_next_assignment_by_distance(effort, user, user_lat, user_lon)`**
Gets nearest assignment using GeoDjango `Distance`. Falls back to haversine. Same locking as `get_next_assignment()`.

## Common Query Patterns

```python
# Person with relations
Person.objects.select_related("voter_record").prefetch_related(
    "phone_numbers", "emails", "addresses"
).get(pk=person_id)

# Spatial queries (lon, lat order!)
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

user_location = Point(-84.388, 33.749, srid=4326)
VoterRecord.objects.filter(location__distance_lte=(user_location, D(mi=0.5)))
VoterRecord.objects.annotate(distance=Distance("location", user_location)).order_by("distance")
District.objects.filter(boundary__contains=point)
```

## Concurrent User Support

Uses `select_for_update(skip_locked=True)` for row-level locking:
```python
with transaction.atomic():
    assignment = EffortAssignment.objects.select_for_update(skip_locked=True).filter(
        effort=effort, status=EffortAssignment.Status.PENDING
    ).first()
    if assignment:
        assignment.status = EffortAssignment.Status.IN_PROGRESS
        assignment.locked_by = user
        assignment.locked_at = timezone.now()
        assignment.save(update_fields=["status", "locked_by", "locked_at"])
```
Features: Multi-user support, atomic transactions, 10-min stale lock auto-release

## HTMX Workflows

**Phone Banking:**
1. Load `/drives/<uuid>/call/` → `calling_session.html`
2. HTMX `hx-get="/call/next/"` → `calling_next` returns `_person_card.html`
3. Submit `hx-post="/call/log/"` → `calling_log` processes, returns next card

**Door Knocking:**
1. Load `/drives/<uuid>/knock/` → `knocking_session.html`
2. GPS prompt stores `knocker_lat`/`knocker_lon` in session
3. HTMX `hx-get="/knock/next/"` → `knocking_next` finds nearest via `get_next_assignment_by_distance()`
4. Submit `hx-post="/knock/log/"` → `knocking_log` processes, returns next card

## Forms (`forms.py`)

- `CampaignForm` - Campaign (org) create/edit
- `DriveForm` / `ContactEffortForm` - Drive create/edit (model: ContactEffort)
- `ContactAttemptForm` - Phone outcomes (radio buttons)
- `DoorKnockAttemptForm` - Door knock outcomes
- `AssignmentFilterForm` - Bulk assignment filters (party, likelihood, has_phone, limit)
- `OfficeForm`, `ElectionForm`, `CandidateForm`, `ElectionDateForm`

## Services

### Geocoding (`services/geocoding.py`)
`CachedGeocodingService` - Redis cache (30-day TTL), OpenCage (primary, 2,500/day), Nominatim (fallback)
```python
from civicpulse.services.geocoding import CachedGeocodingService
service = CachedGeocodingService()
result = service.geocode("123 Main St, Atlanta, GA 30303")
# Returns: {"latitude": 33.749, "longitude": -84.388, "confidence": 0.95}
```

### Routing (`services/routing.py`)
`RouteOptimizer` - Cascading fallback: Local OSRM → OpenRouteService → OSRM Demo → Nearest Neighbor
1-hour result caching, TSP optimization, walking profile, route geometry

## Celery Tasks (`tasks.py`)

- `geocode_single_address(model_type, model_id, address_text, job_id)` - Auto-retry (max 3), exponential backoff
- `geocode_batch(addresses, job_id, rate_limit_seconds)` - Rate-limited batch processing
- `geocode_election_voters(election_id, job_id, batch_size)` - Batch geocoding with error logging
- `geocode_import_job_voters(import_job_id, rate_limit_seconds)` - Chains from CSV import

## Management Commands

### Import Voters
```bash
uv run python manage.py import_voters path/to/file.csv [--dry-run]
```
Matches by `voter_id`, creates/updates Person/VoterRecord/Address/PhoneNumber. Progress every 100 rows, stops after 10 errors.

### Import TIGER Shapefiles (CLI)
```bash
uv sync --extra geo  # Install GIS dependencies
uv run python manage.py import_tiger_shapefile \
    data/tl_2024_13_county/tl_2024_13_county.shp \
    --district-type county --state GA --effective-date 2024-01-01 [--dry-run] [--update-existing]
```
Options: `--district-type` (required), `--state`, `--identifier-field` (default: GEOID), `--name-field` (default: NAME), `--effective-date`, `--source`, `--verbose`

### Import Districts (Django Admin)
1. Admin → District Import Jobs → Add
2. Enter census.gov URL (e.g., `https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip`)
3. Select district type, state (optional)
4. Save → Select job → Actions → "Trigger import"
5. Monitor: Pending → Downloading → Processing → Completed/Failed

Example URLs:
- Counties: `https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip`
- Congressional: `https://www2.census.gov/geo/tiger/TIGER2024/CD/tl_2024_us_cd118.zip`
- State House: `https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_13_sldl.zip`

## Environment Configuration

**Use .env file:** `cp .env.example .env`

**Required (prod):**
- `SECRET_KEY` - Generate: `uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `DATABASE_URL` - PostgreSQL/PostGIS connection
- `DB_ENGINE` - `django.contrib.gis.db.backends.postgis`

**Optional:**
- `DEBUG` (default: false), `ALLOWED_HOSTS` (default: localhost,127.0.0.1)
- `REDIS_URL` (default: redis://localhost:6379/1)
- `CELERY_BROKER_URL` (default: redis://localhost:6379/0)
- `OPENCAGE_API_KEY` - Geocoding (2,500/day free)
- `OPENROUTESERVICE_API_KEY` - Routing (2,000/day free)
- `OSRM_URL` - Local OSRM server
- `GDAL_LIBRARY_PATH`, `SPATIALITE_LIBRARY_PATH` (if auto-detect fails)

## GIS Setup

**Ubuntu/Debian:**
```bash
sudo apt install gdal-bin libgdal-dev libgeos-dev libproj-dev libsqlite3-mod-spatialite
```

**macOS:**
```bash
brew install gdal geos proj spatialite-tools
```

**Environment (if needed):**
```bash
export GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
export SPATIALITE_LIBRARY_PATH=/usr/lib/mod_spatialite.so
```

## Admin Interface

- `PersonAdmin` - TabularInline (phone/email/address), StackedInline (VoterRecord)
- `ElectionAdmin` - CandidateInline, ElectionDateInline, `trigger_geocoding` action
- `CampaignAdmin` - ContactEffortInline, drive count
- `ContactEffortAdmin` - Assignment inline, stats
- `GeocodingJobAdmin` - Progress, success rate, retry action
- `DistrictImportJobAdmin` - URL validation, async import trigger, error display

## Testing

```bash
uv run python manage.py test
```
**Note:** Requires PostgreSQL/PostGIS. SpatiaLite in-memory has trigger issues.

Test classes: `AssignmentAddViewTests`, `CandidateDetailTests`, `CallingSessionTests`, `KnockingSessionTests`, `AssignmentListTests`, `GetAssignmentTargetHelperTests`

## Security

- Authentication: `@login_required` on all views
- CSRF: `{% csrf_token %}` in forms
- SQL Injection: Django ORM parameterized queries
- XSS: Template auto-escaping
- Locking: Row-level locks prevent race conditions
- Stale locks: 10-min timeout prevents DoS

## Database Indexes

- `Person`: (last_name, first_name)
- `ContactAttempt`: (effort, person), (effort, outcome)
- `EffortAssignment`: (effort, status), (locked_by, locked_at)
