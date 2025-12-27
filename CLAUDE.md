# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CivicPulse is a Django-based contact management, election tracking, and campaign orchestration platform designed for civic organizations and nonprofits. It provides voter contact data management, election and candidate tracking, campaign creation, and HTMX-powered multi-channel outreach workflows (phone banking, texting, and door knocking) with concurrent user support using database row-level locking.

**Tech Stack:**
- Backend: Django 6.0+, Python 3.13+, GeoDjango
- Frontend: Tailwind CSS 4.1+, Flowbite components, HTMX 2.0.4, Leaflet.js
- Database: SpatiaLite (dev), PostGIS/PostgreSQL (prod)
- Task Queue: Celery with Redis
- CSS Compilation: django-compressor
- Dependency Management: uv (Python), npm (Node)

## Development Commands

**Always use `uv` for Python operations:**
```bash
uv sync                              # Install/sync dependencies
uv run python manage.py runserver    # Start dev server
uv run python manage.py migrate      # Run migrations
uv run python manage.py createsuperuser  # Create admin user
```

**Tailwind CSS:**
```bash
npm install                          # Install Node dependencies
npx @tailwindcss/cli -i static/src/input.css -o static/src/output.css --watch  # Watch mode
```

**Code formatting/linting:**
```bash
uv run black .                       # Format Python
uv run ruff check .                  # Lint Python
uv run djlint .                      # Lint templates
```

**Testing:**
```bash
uv run python manage.py test         # Run tests (tests not yet implemented)
```

**Celery (background tasks):**
```bash
uv run celery -A example worker -l info       # Start worker
uv run celery -A example beat -l info         # Start scheduler (for periodic tasks)
```

## GIS System Dependencies

GeoDjango requires system-level GIS libraries. Install before running migrations:

**Ubuntu/Debian:**
```bash
sudo apt install gdal-bin libgdal-dev libgeos-dev libproj-dev libsqlite3-mod-spatialite
```

**macOS (Homebrew):**
```bash
brew install gdal geos proj spatialite-tools
```

**Environment variables (if libraries not auto-detected):**
```bash
export GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
export SPATIALITE_LIBRARY_PATH=/usr/lib/mod_spatialite.so
```

## Environment Configuration

Configuration uses **python-decouple** following 12-Factor App principles:

1. **Environment Variables** (highest priority) - Production/CI
2. **.env file** - Local development convenience
3. **Code defaults** - Fallback only

**Quick Start:**
```bash
cp .env.example .env                    # Copy template
# Edit .env with your settings, then:
uv run python manage.py runserver       # Settings loaded automatically
```

**Key Configuration Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes* | dev-only key | Django secret (generate for prod) |
| `DEBUG` | No | `false` | Enable debug mode |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated hosts |
| `DB_ENGINE` | No | auto-detect | Database backend |
| `REDIS_URL` | No | `redis://localhost:6379/1` | Cache backend |
| `CELERY_BROKER_URL` | No | `redis://localhost:6379/0` | Task queue |

**Optional API Keys:**

| Variable | Service | Purpose |
|----------|---------|---------|
| `OPENROUTESERVICE_API_KEY` | [OpenRouteService](https://openrouteservice.org/) | Route optimization fallback |
| `OPENCAGE_API_KEY` | [OpenCage](https://opencagedata.com/) | Geocoding addresses |

*A dev-only default is provided, but production MUST set a secure key.

**Generate SECRET_KEY:**
```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Project Structure

```
civicpulse-backend/
├── src/civicpulse/                # Main Django app (src-layout)
│   ├── models.py                  # Core data models (15+ models)
│   ├── views.py                   # View functions (50+ views)
│   ├── urls.py                    # URL routing
│   ├── forms.py                   # Django forms
│   ├── admin.py                   # Django admin config
│   ├── tasks.py                   # Celery background tasks
│   ├── conf.py                    # App configuration/defaults
│   ├── services/                  # Business logic services
│   │   ├── geocoding.py           # Geocoding service (OpenCage/Nominatim)
│   │   └── routing.py             # Route optimization (OSRM)
│   ├── management/
│   │   └── commands/
│   │       └── import_voters.py   # CSV bulk import command
│   └── templates/civicpulse/
│       ├── base.html              # Base template with nav & CDN libs
│       ├── index.html             # Home page
│       ├── registration/
│       │   └── login.html         # Login page
│       ├── campaigns/
│       │   ├── campaign_list.html
│       │   ├── campaign_detail.html
│       │   ├── knocking_session.html      # Door knocking with route map
│       │   ├── calling_session.html       # Phone banking interface
│       │   └── partials/
│       │       ├── _person_card.html      # Phone: person + outcome form
│       │       ├── _address_card.html     # Door: address + outcome form
│       │       └── _progress_bar.html     # Reusable progress bar
│       ├── maps/
│       │   └── partials/
│       │       ├── _map_container.html    # Reusable Leaflet map container
│       │       └── _map_init.html         # Map initialization script
│       └── elections/
│           ├── election_list.html
│           ├── election_detail.html
│           └── ...
├── example_project/example/       # Django project config
│   ├── settings.py               # Django settings (GeoDjango config)
│   ├── celery.py                 # Celery app configuration
│   ├── urls.py                   # Root URL config
│   └── wsgi.py                   # WSGI app entry
├── static/src/
│   ├── input.css                 # Tailwind source
│   └── output.css                # Compiled Tailwind
├── pyproject.toml                # uv/Python config
├── package.json                  # Node dependencies
└── db.sqlite3                    # Dev database (SpatiaLite)
```

## Architecture

**Frontend stack:**
- Tailwind CSS with django-compressor for bundling
- Flowbite components (loaded from CDN)
- HTMX 2.0.4 for seamless partial page updates
- Leaflet.js for interactive maps (loaded from CDN)
- Templates use `{% compress css %}` for CSS processing

**Authentication:**
- Django's built-in auth with `@login_required` on all views
- Login/logout at `/login/` and `/logout/`
- Users created via Django admin only
- `LOGIN_URL = "login"`, `LOGIN_REDIRECT_URL = "/"`

**Database:**
- SpatiaLite by default (db.sqlite3) - GeoDjango spatial extension
- PostGIS/PostgreSQL for production
- All models use UUID primary keys
- Spatial fields use SRID 4326 (WGS84)

**GIS/Spatial:**
- GeoDjango with `django.contrib.gis` for spatial database operations
- PointField for voter/address locations
- MultiPolygonField for district boundaries
- Database-level spatial queries (distance, containment)
- OSRM for road-aware route optimization

**Background Tasks:**
- Celery with Redis broker for async processing
- Geocoding tasks with rate limiting and retry logic
- Batch processing for bulk imports

## Data Models

### Person (`civicpulse/models.py:7-53`)
Core contact record with UUID primary key.

**Fields:**
- `first_name`, `last_name`, `middle_name`, `nickname` (CharField)
- `organization`, `job_title` (CharField)
- `voter_id` (CharField, unique) - External voter file ID for CSV matching
- `user` (OneToOneField → Django User, optional) - Link to user account

**Related models:**
- `phone_numbers` → PhoneNumber (ForeignKey)
- `emails` → Email (ForeignKey)
- `addresses` → Address (ForeignKey)
- `voter_record` → VoterRecord (OneToOne)
- `contact_attempts` → ContactAttempt (ForeignKey)
- `effort_assignments` → EffortAssignment (ForeignKey)

### PhoneNumber (`civicpulse/models.py:55-79`)
- `person` (ForeignKey → Person, CASCADE)
- `number` (CharField, max 20)
- `type` (choices: mobile/home/work/other)
- `is_primary` (BooleanField)

### Email (`civicpulse/models.py:81-102`)
- `person` (ForeignKey → Person, CASCADE)
- `email` (EmailField)
- `type` (choices: personal/work/other)
- `is_primary` (BooleanField)

### Address (`civicpulse/models.py:104-132`)
- `person` (ForeignKey → Person, CASCADE)
- `type` (choices: home/work/mailing)
- `street_address`, `street_address_2`, `city`, `state` (2-char), `zip_code`
- `is_primary` (BooleanField)

### VoterRecord (`civicpulse/models.py`)
OneToOne with Person, stores comprehensive voter data.

**Demographics:**
- `registered_party`, `gender`, `age`, `ethnicity`, `marital_status`
- `spoken_language`, `military_status`, `changed_party`

**Location (GIS):**
- `location` (PointField, geography=True, srid=4326) - GeoDjango spatial field
- `latitude`, `longitude` (DecimalField) - Legacy fields for backwards compatibility
- `apartment_type`, `street_number_parity`

**Voting Scores** (stored as strings like "77%"):
- `likelihood_general`, `likelihood_primary`, `likelihood_combined`

**Voting History (booleans):**
- `voted_general_2024/2022/2020/2018`
- `voted_primary_2024/2022/2020/2018`

**Household:**
- `household_party`, `mailing_household_size`, `mailing_family_id`
- `mailing_household_count`, `mailing_household_party`

### Office (`civicpulse/models.py:197-240`)
Represents an elected position (e.g., "Mayor", "City Council Seat 3").

- `name` (CharField) - Office title
- `level` (TextChoices: federal/state/county/city/school_district/other)
- `city`, `county`, `state` (CharField) - Jurisdiction fields
- `term_length_years` (PositiveIntegerField, optional)
- `description` (TextField)

**Related models:**
- `elections` → Election (ForeignKey)

### Election (`civicpulse/models.py:243-305`)
A specific election race for an office.

- `office` (ForeignKey → Office, CASCADE)
- `election_type` (TextChoices: general/primary/special/runoff)
- `year` (PositiveIntegerField)
- `parent_election` (ForeignKey → self, SET_NULL) - Links primaries to generals
- `status` (TextChoices: upcoming/active/completed/certified)

**Key Date Fields:**
- `qualifying_start`, `qualifying_end` (DateField)
- `registration_deadline`, `absentee_request_deadline` (DateField)
- `early_voting_start`, `early_voting_end` (DateField)
- `election_day`, `certification_date` (DateField)

**Related models:**
- `candidates` → Candidate (ForeignKey)
- `additional_dates` → ElectionDate (ForeignKey)
- `contact_efforts` → ContactEffort (ForeignKey)

### ElectionDate (`civicpulse/models.py:308-336`)
Flexible additional dates for an election (debates, forums, etc.).

- `election` (ForeignKey → Election, CASCADE)
- `date_type` (TextChoices: candidate_forum/debate/filing_deadline/campaign_event/fundraising_deadline/other)
- `date` (DateField)
- `description`, `location` (CharField)

### Candidate (`civicpulse/models.py:339-377`)
Links a Person to an Election as a candidate.

- `person` (ForeignKey → Person, CASCADE)
- `election` (ForeignKey → Election, CASCADE)
- `party_affiliation` (CharField)
- `is_incumbent` (BooleanField)
- `status` (TextChoices: active/withdrawn/won/lost)
- `campaign_website` (URLField)
- `campaign_slogan` (CharField)
- `unique_together = ["person", "election"]`

**Related models:**
- `contact_efforts` → ContactEffort (ForeignKey)

### ContactEffort (`civicpulse/models.py:380-420`)
Represents an outreach campaign (e.g., "2024 GOTV Phone Bank").

- `name`, `description`, `script` (caller talking points)
- `is_active` (BooleanField)
- `election` (ForeignKey → Election, SET_NULL, optional) - Associated election
- `candidate` (ForeignKey → Candidate, SET_NULL, optional) - Supported candidate
- `created_by` (ForeignKey → User)

### ContactAttempt (`civicpulse/models.py:443-510`)
Logs each contact attempt within a campaign.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person)
- `contact_type`: "call", "text", or "door_knock"
- `outcome` choices:
  - **Phone/Text outcomes:**
    - `no_answer` - No Answer (retry eligible)
    - `busy` - Busy Signal (retry eligible)
    - `left_voicemail` - Left Voicemail (retry eligible)
    - `callback_requested` - Callback Requested (retry eligible)
    - `wrong_number` - Wrong Number (terminal)
    - `spoke_with` - Spoke With Person (terminal)
    - `will_vote` - Will Vote for Candidate (terminal)
    - `refused` - Refused/Do Not Contact (terminal)
  - **Door knock outcomes:**
    - `not_home` - Not Home (retry eligible)
    - `left_door_hanger` - Left Door Hanger (retry eligible)
    - `spoke_at_door` - Spoke at Door (terminal)
    - `refused_door` - Refused to Answer Door (terminal)
    - `no_access` - No Access/Gated (retry eligible)
- `notes`, `callback_time`, `phone_number_used`
- `address_visited` (ForeignKey → Address, optional) - For door knock attempts

**Terminal outcomes:** `TERMINAL_OUTCOMES = [spoke_with, will_vote, refused, wrong_number, spoke_at_door, refused_door]`

### EffortAssignment (`civicpulse/models.py`)
Pre-assigns persons to campaigns with locking support.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person)
- `status`: pending → in_progress → completed
- `locked_by` / `locked_at`: Prevents concurrent callers from getting same person
- `unique_together = ["effort", "person"]`

### District (`civicpulse/models.py`) - GIS Model
Represents voting precincts, congressional districts, etc. with geographic boundaries.

- `name` (CharField) - Display name
- `district_type` (TextChoices: precinct/congressional/state_house/state_senate/county/city)
- `identifier` (CharField) - Official district code
- `state`, `county` (CharField) - Jurisdiction
- `boundary` (MultiPolygonField, srid=4326) - Geographic boundary polygon
- `source` (CharField) - Data source (e.g., "Census Bureau TIGER")
- `effective_date` (DateField) - When boundaries took effect

**Spatial Queries:**
```python
from django.contrib.gis.geos import Point
point = Point(-84.388, 33.749, srid=4326)
District.objects.filter(boundary__contains=point)  # Districts containing point
```

### GeocodingJob (`civicpulse/models.py`) - GIS Model
Tracks bulk geocoding operations for elections.

- `election` (ForeignKey → Election)
- `status` (TextChoices: pending/running/completed/failed)
- `total_addresses`, `processed_count`, `success_count`, `error_count` (IntegerField)
- `created_by` (ForeignKey → User)
- `started_at`, `completed_at` (DateTimeField)

### GeocodingError (`civicpulse/models.py`) - GIS Model
Logs failed geocoding attempts for review and retry.

- `job` (ForeignKey → GeocodingJob)
- `address_text` (CharField) - The address that failed
- `error_message` (TextField) - Error details
- `model_type` (CharField) - "VoterRecord", "Address", etc.
- `model_id` (UUIDField) - ID of the record that failed

## Common Access Patterns

```python
# Person with contact info
person = Person.objects.select_related("voter_record").prefetch_related(
    "phone_numbers", "emails", "addresses"
).get(pk=person_id)

person.phone_numbers.all()                    # Get all phone numbers
person.emails.filter(is_primary=True)         # Get primary email
person.addresses.filter(type='home')          # Get home addresses
person.voter_record                           # Get voter record (OneToOne)

# Filter by voter data
Person.objects.filter(voter_record__registered_party='Democratic')

# Campaign with stats
campaign = ContactEffort.objects.annotate(
    total_assignments=Count("assignments"),
    pending_count=Count("assignments", filter=Q(assignments__status="pending")),
    completed_count=Count("assignments", filter=Q(assignments__status="completed")),
).get(pk=campaign_id)

# Efficient person fetch for calling
Person.objects.select_related("voter_record").prefetch_related(
    "phone_numbers",
    "addresses",
    Prefetch(
        "contact_attempts",
        queryset=ContactAttempt.objects.filter(effort=effort).order_by("-created_at")[:5],
        to_attr="effort_attempts",
    ),
)

# --- Spatial Queries (GeoDjango) ---

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

# Create a point from coordinates (lon, lat order!)
user_location = Point(-84.388, 33.749, srid=4326)

# Find voters within 0.5 miles radius
VoterRecord.objects.filter(
    location__distance_lte=(user_location, D(mi=0.5))
)

# Sort by distance from user
VoterRecord.objects.annotate(
    distance=Distance("location", user_location)
).order_by("distance")

# Find voters within a district boundary
district = District.objects.get(name="Precinct 42")
VoterRecord.objects.filter(location__within=district.boundary)
```

## URL Routes

**Full route structure:**
```
/                                        → index (home page)
/login/                                  → Django auth login
/logout/                                 → Django auth logout
/admin/                                  → Django admin

/campaigns/                              → campaign_list
/campaigns/create/                       → campaign_create
/campaigns/<uuid:pk>/                    → campaign_detail
/campaigns/<uuid:pk>/edit/               → campaign_edit
/campaigns/<uuid:pk>/delete/             → campaign_delete
/campaigns/<uuid:pk>/assignments/        → assignment_list
/campaigns/<uuid:pk>/assignments/add/    → assignment_add
/campaigns/<uuid:pk>/assignments/remove/ → assignment_remove (POST only)
/campaigns/<uuid:pk>/call/               → calling_session
/campaigns/<uuid:pk>/call/next/          → calling_next (HTMX)
/campaigns/<uuid:pk>/call/log/           → calling_log (HTMX POST)
/campaigns/<uuid:pk>/call/skip/          → calling_skip (HTMX POST)
/campaigns/<uuid:pk>/knock/              → knocking_session
/campaigns/<uuid:pk>/knock/location/     → knocking_set_location (HTMX POST)
/campaigns/<uuid:pk>/knock/next/         → knocking_next (HTMX)
/campaigns/<uuid:pk>/knock/log/          → knocking_log (HTMX POST)
/campaigns/<uuid:pk>/knock/skip/         → knocking_skip (HTMX POST)

/offices/                                → office_list
/offices/create/                         → office_create
/offices/<uuid:pk>/                      → office_detail
/offices/<uuid:pk>/edit/                 → office_edit
/offices/<uuid:pk>/delete/               → office_delete

/elections/                              → election_list
/elections/create/                       → election_create
/elections/<uuid:pk>/                    → election_detail
/elections/<uuid:pk>/edit/               → election_edit
/elections/<uuid:pk>/delete/             → election_delete
/elections/<uuid:pk>/campaigns/          → election_campaigns
/elections/<uuid:pk>/dates/add/          → election_date_add
/elections/<uuid:pk>/dates/<uuid>/delete/→ election_date_delete
/elections/<uuid:pk>/candidates/         → candidate_list
/elections/<uuid:pk>/candidates/add/     → candidate_add

/candidates/<uuid:pk>/                   → candidate_detail
/candidates/<uuid:pk>/edit/              → candidate_edit
/candidates/<uuid:pk>/delete/            → candidate_delete

# GeoJSON API Endpoints
/api/campaigns/<uuid:pk>/locations/      → api_campaign_locations (FeatureCollection)
/api/campaigns/<uuid:pk>/route/          → api_campaign_route (optimized walking route)
/api/elections/<uuid:pk>/voter-distribution/ → api_election_voter_distribution
/api/districts/                          → api_districts (boundary polygons)
```

## View Helper Functions

Located in `civicpulse/views.py`:

### `get_next_assignment(effort, user)` (lines 673-701)
Core lock acquisition logic for concurrent users.
- Releases stale locks (>10 min old)
- Uses `select_for_update(skip_locked=True)` for row-level locking
- Returns locked assignment or None

### `get_person_with_details(person_id, effort)` (lines 704-720)
Efficiently fetches person with all contact-relevant data.
- Uses select_related + prefetch_related
- Prefetches last 5 attempts for this effort

### `get_session_stats(effort)` (lines 723-737)
Calculates campaign progress stats.
- Returns: total, pending, in_progress, completed, percentage, remaining

### `haversine_distance(lat1, lon1, lat2, lon2)`
Calculates great-circle distance between two GPS coordinates.
- Returns distance in miles
- Legacy fallback when GeoDjango unavailable

### `get_next_assignment_by_distance(effort, user, user_lat, user_lon)`
Gets next assignment sorted by proximity to user's location.
- Uses GeoDjango `Distance` function for database-level sorting
- Falls back to haversine if spatial fields unavailable
- Uses same row-level locking as `get_next_assignment()`

### `get_voters_within_radius(center_point, radius_miles, queryset=None)`
Returns voters within specified radius of a point.
- Uses GeoDjango `distance_lte` lookup
- Returns VoterRecord queryset

### `get_voters_in_district(district, queryset=None)`
Returns voters located within a district boundary.
- Uses GeoDjango `within` lookup
- Works with any District (precinct, congressional, etc.)

### `get_election_voters_in_district(election, district)`
Returns ElectionVoters for an election within a district.
- Combines election filtering with spatial containment

## Concurrent User Support

Uses `select_for_update(skip_locked=True)` for row-level locking, enabling multiple callers or door knockers to work the same campaign simultaneously:

```python
with transaction.atomic():
    assignment = (
        EffortAssignment.objects.select_for_update(skip_locked=True)
        .filter(effort=effort, status=EffortAssignment.Status.PENDING)
        .first()
    )
    if assignment:
        assignment.status = EffortAssignment.Status.IN_PROGRESS
        assignment.locked_by = user
        assignment.locked_at = timezone.now()
        assignment.save(update_fields=["status", "locked_by", "locked_at"])
```

**Features:**
- Skips locked rows, allowing multiple concurrent users (callers + door knockers)
- Atomic transaction ensures only one user gets each person
- 10-minute stale lock timeout auto-releases abandoned sessions
- Same locking mechanism used by both phone banking and door knocking

## HTMX Calling Workflow

1. User loads `/campaigns/<uuid>/call/` → `calling_session.html`
2. HTMX triggers `hx-get="/call/next/"` on load
3. `calling_next` returns person card partial with form
4. User selects outcome and submits via `hx-post="/call/log/"`
5. `calling_log` processes outcome, releases lock, calls `calling_next`
6. `calling_next` returns next person card or completion message

## HTMX Door Knocking Workflow

1. User loads `/campaigns/<uuid>/knock/` → `knocking_session.html`
2. Location picker prompts for GPS (browser Geolocation API) or manual skip
3. On GPS success, coordinates stored in session and `knocking_next` triggered
4. `knocking_next` finds nearest pending assignment using `get_next_assignment_by_distance()`
5. Returns `_address_card.html` with address, map link, distance indicator, and outcome form
6. User selects outcome (Spoke at Door, Not Home, Left Hanger, etc.) and submits via `hx-post="/knock/log/"`
7. `knocking_log` processes outcome, releases lock, calls `knocking_next`
8. `knocking_next` returns next nearest address or completion message

**Location handling:**
- GPS coordinates stored in Django session (`knocker_lat`, `knocker_lon`)
- User can update location at any time via "Update" button
- Without GPS, falls back to regular sequential assignment

## Forms (`civicpulse/forms.py`)

- `CampaignForm` - Create/edit campaigns
- `ContactAttemptForm` - Log phone call outcomes with radio buttons
- `DoorKnockAttemptForm` - Log door knock outcomes (Not Home, Spoke at Door, Left Hanger, etc.)
- `AssignmentFilterForm` - Filter persons for bulk assignment
  - Filters: party, likelihood (high/medium/low), has_phone, limit
- `OfficeForm` - Create/edit elected offices
- `ElectionForm` - Create/edit elections with date fields
- `CandidateForm` - Add/edit candidates for elections
- `ElectionDateForm` - Add additional dates to elections

## Templates

**Base template (`_base.html`):**
- Tailwind CSS via compressor
- CDN: Flowbite JS, HTMX 2.0.4
- Green-50 background, navigation bar

**Calling interface (`campaigns/`):**
- `calling_session.html` - Phone banking session page
- `partials/_person_card.html` - Person display with phone + call outcome form
- `partials/_session_complete.html` - Phone session completion message

**Door knocking interface (`campaigns/`):**
- `knocking_session.html` - Door knocking session page with GPS location picker
- `partials/_address_card.html` - Address display with map link + distance + knock outcome form
- `partials/_knocking_complete.html` - Knocking session completion message

**Shared partials (`campaigns/partials/`):**
- `_progress_bar.html` - Reusable progress bar (used by both interfaces)

## Management Commands

### Import Voters (`import_voters.py`)
```bash
uv run python manage.py import_voters path/to/file.csv           # Run import
uv run python manage.py import_voters path/to/file.csv --dry-run # Validate only
```

**Functionality:**
- Matches/creates Person records by voter_id
- Creates/updates VoterRecord, Address (home + mailing), PhoneNumber
- Reports progress every 100 rows
- Stops after 10 errors with row-level details
- Uses atomic transactions per row

**Expected CSV columns:** Voter ID, First Name, Last Name, Address, City, State, Zipcode, Cell Phone, Registered Party, Gender, Age, Ethnicity, voting history fields, etc.

## Admin Interface

- `PersonAdmin` with TabularInline for phone/email/address and StackedInline for VoterRecord
- `OfficeAdmin` with election count display
- `ElectionAdmin` with CandidateInline, ElectionDateInline, and geocoding status
  - `trigger_geocoding` action - Start geocoding job for election voters
- `CandidateAdmin` with raw_id_fields for person/election
- `ContactEffortAdmin` with assignment inline, election/candidate fields, and stats
- `ContactAttemptAdmin` with raw_id_fields for person lookup
- `GeocodingJobAdmin` with progress display, success rate, and retry action
- `DistrictAdmin` with boundary management

## Services

### Geocoding Service (`civicpulse/services/geocoding.py`)

Provides address-to-coordinates conversion with caching and fallback.

**Classes:**
- `CachedGeocodingService` - Main interface with Redis caching (30-day TTL)
- `OpenCageGeocodingService` - Primary provider (2,500 free requests/day)
- `NominatimGeocodingService` - Free fallback with rate limiting

**Usage:**
```python
from civicpulse.services.geocoding import CachedGeocodingService

service = CachedGeocodingService()
result = service.geocode("123 Main St, Atlanta, GA 30303")
# Returns: {"latitude": 33.749, "longitude": -84.388, "confidence": 0.95}
```

### Routing Service (`civicpulse/services/routing.py`)

Provides road-aware route optimization with cascading fallback.

**Routing Chain** (tries in order until one succeeds):
1. **Local OSRM** (if `OSRM_URL` configured) - Self-hosted, no rate limits
2. **OpenRouteService** (if `OPENROUTESERVICE_API_KEY` configured) - 2,000 req/day free
3. **OSRM Demo Server** - Public fallback, rate-limited
4. **Nearest Neighbor** - Always works, uses straight-line distance

**Classes:**
- `OSRMRoutingService` - OSRM Trip API for TSP optimization
- `OpenRouteServiceRouter` - ORS Directions API with walking profile
- `NearestNeighborRouter` - Simple greedy fallback
- `RouteOptimizer` - Main service with caching and fallback chain

**Features:**
- Traveling salesman optimization
- Walking profile for door knocking
- Route geometry for map display
- Distance and duration estimates
- 1-hour result caching

**Configuration** (`CIVICPULSE` settings dict):
```python
CIVICPULSE = {
    "OSRM_URL": "http://localhost:5000",  # Local OSRM (optional)
    "OPENROUTESERVICE_API_KEY": "your-key",  # ORS API key (optional)
}
# If neither configured, uses OSRM demo server automatically
```

**Usage:**
```python
from civicpulse.services.routing import RouteOptimizer, Waypoint

optimizer = RouteOptimizer(effort_id=str(campaign.pk), user_id=request.user.id)
route = optimizer.get_optimized_route(
    waypoints=[Waypoint(id="1", latitude=33.749, longitude=-84.388, ...)],
    start_lat=33.750,
    start_lon=-84.390,
)
# route.source indicates which router succeeded: "local_osrm", "openrouteservice", "osrm_demo", or "nearest_neighbor"
```

## Celery Tasks (`civicpulse/tasks.py`)

Background tasks for geocoding and data processing.

### `geocode_single_address(model_type, model_id, address_text, job_id=None)`
Geocodes a single address and updates the model's location field.
- Auto-retry with exponential backoff (max 3 retries)
- Updates GeocodingJob progress if job_id provided

### `geocode_batch(addresses, job_id=None, rate_limit_seconds=1.0)`
Processes a batch of addresses with rate limiting.
- Respects API rate limits (default 1 req/sec)
- Updates batch progress atomically

### `geocode_election_voters(election_id, job_id=None, batch_size=100)`
Geocodes all ElectionVoters for an election lacking coordinates.
- Creates GeocodingJob for tracking
- Processes in batches to avoid memory issues
- Logs errors for failed addresses

### `geocode_import_job_voters(import_job_id, rate_limit_seconds=1.0)`
Chains from import task to geocode newly imported voters.
- Triggered after CSV import completes
- Only geocodes voters without existing coordinates

## Security Considerations

1. **Authentication:** All views require `@login_required`
2. **CSRF:** Forms include `{% csrf_token %}`
3. **SQL Injection:** Django ORM uses parameterized queries
4. **XSS:** Templates use auto-escaping
5. **Locking:** Database row-level locks prevent race conditions
6. **Stale Lock Release:** Prevents DoS from abandoned sessions

## Database Indexes

Important indexes for performance:
- `Person`: (last_name, first_name)
- `ContactAttempt`: (effort, person), (effort, outcome)
- `EffortAssignment`: (effort, status), (locked_by, locked_at)

## Testing

Tests are located in `civicpulse/tests.py` (not yet implemented).

```bash
uv run python manage.py test
```

## Environment Variables

For production, configure via `.env`:

**Django:**
- `SECRET_KEY` - Django secret key
- `DEBUG` - Set to False
- `ALLOWED_HOSTS` - Comma-separated hostnames

**Database:**
- `DATABASE_URL` - PostgreSQL/PostGIS connection string
- `DB_ENGINE` - `django.contrib.gis.db.backends.postgis` for production

**GIS Libraries (if not auto-detected):**
- `GDAL_LIBRARY_PATH` - Path to GDAL library (e.g., `/usr/lib/libgdal.so`)
- `SPATIALITE_LIBRARY_PATH` - Path to SpatiaLite module

**Geocoding:**
- `OPENCAGE_API_KEY` - OpenCage geocoding API key (2,500 free/day)

**Routing:**
- `OSRM_URL` - Local OSRM server URL (e.g., `http://localhost:5000`)
- `OPENROUTESERVICE_API_KEY` - OpenRouteService API key (2,000 free/day)
- If neither configured, uses public OSRM demo server as fallback

**Cache/Task Queue:**
- `REDIS_URL` - Redis connection for caching and Celery broker
- `CELERY_BROKER_URL` - Celery broker (defaults to REDIS_URL)
