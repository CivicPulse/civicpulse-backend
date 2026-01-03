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

## User Notes

- Consider any needed chnages to user or developer documentation when modifying functionality.

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
│       ├── org_campaigns/         # Campaign (organization) templates
│       │   ├── campaign_list.html
│       │   ├── campaign_detail.html
│       │   ├── campaign_form.html
│       │   └── campaign_confirm_delete.html
│       ├── campaigns/             # Drive (ContactEffort) templates
│       │   ├── campaign_list.html         # Drive list
│       │   ├── campaign_detail.html       # Drive detail
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

## Terminology

| Term | Definition | Code Model |
|------|------------|------------|
| **Campaign** | Organization working to elect a candidate or advance an issue | `Campaign` |
| **Drive** | Specific voter outreach effort (phone bank, canvass) | `ContactEffort` |
| **Race** | An election for a specific office | `Election` |

**Hierarchy:**
```
Campaign ("Smith for Mayor 2024")
├── Drive 1 ("October Phone Bank")
│   ├── Assignments
│   └── Contact Attempts
├── Drive 2 ("Weekend Canvass")
│   └── ...
└── Drive 3 ("Election Day GOTV")
    └── ...
```

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

- `person` (ForeignKey → Person, **SET_NULL**, nullable) - Preserves candidate record if person deleted
- `election` (ForeignKey → Election, CASCADE)
- `party_affiliation` (CharField)
- `is_incumbent` (BooleanField)
- `status` (TextChoices: active/withdrawn/won/lost)
- `campaign_website` (URLField)
- `campaign_slogan` (CharField)
- `unique_together = ["person", "election"]`

**Design note:** `on_delete=SET_NULL` ensures candidate history is preserved even if the linked Person record is deleted. Views handle `person=None` gracefully.

**Related models:**
- `campaigns` → Campaign (ForeignKey)
- `contact_efforts` → ContactEffort (ForeignKey)

### Campaign (`civicpulse/models.py`)
Represents the organization/effort to elect a candidate or advance an issue. Groups multiple Drives (ContactEfforts) under one umbrella.

- `name` (CharField) - Campaign name (e.g., "Smith for Mayor 2024")
- `description` (TextField)
- `candidate` (ForeignKey → Candidate, optional) - Supported candidate
- `election` (ForeignKey → Election, optional) - Associated election
- `is_active` (BooleanField)
- `created_by` (ForeignKey → User)
- `created_at`, `updated_at` (DateTimeField)

**Design notes:**
- `candidate` is optional → allows issue-based campaigns (voter registration, ballot measures)
- `election` is optional → allows non-election campaigns
- Multiple campaigns per candidate allowed → separate primary vs general campaigns

**Related models:**
- `drives` → ContactEffort (ForeignKey via `campaign`)

### ContactEffort (`civicpulse/models.py`) - "Drive"
Represents a specific voter outreach effort (e.g., "October GOTV Phone Bank"). In the UI, this is called a "Drive".

- `name`, `description`, `script` (caller talking points)
- `is_active` (BooleanField)
- `campaign` (ForeignKey → Campaign, SET_NULL, optional) - Parent campaign this drive belongs to
- `election` (ForeignKey → Election, SET_NULL, optional) - Associated election
- `candidate` (ForeignKey → Candidate, SET_NULL, optional) - Supported candidate
- `created_by` (ForeignKey → User)

### ContactAttempt (`civicpulse/models.py:443-510`)
Logs each contact attempt within a campaign. Supports **dual-target polymorphism** matching EffortAssignment.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person, **nullable**) - For Person-based contacts
- `election_voter` (ForeignKey → ElectionVoter, **nullable**) - For ElectionVoter-based contacts
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
- `address_visited` (ForeignKey → Address, optional) - For Person door knock attempts
- `voter_address_visited` (ForeignKey → VoterAddress, optional) - For ElectionVoter door knock attempts

**Terminal outcomes:** `TERMINAL_OUTCOMES = [spoke_with, will_vote, refused, wrong_number, spoke_at_door, refused_door]`

### EffortAssignment (`civicpulse/models.py`)
Pre-assigns contact targets to drives with locking support. Supports **dual-target polymorphism** - can reference either a Person or an ElectionVoter.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person, **nullable**) - For non-election drives
- `election_voter` (ForeignKey → ElectionVoter, **nullable**) - For election-based drives
- `status`: pending → in_progress → completed
- `locked_by` / `locked_at`: Prevents concurrent callers from getting same target

**Dual-Target System:**
- Election-based drives (`ContactEffort.election` is set) → assignments use `election_voter`
- Non-election drives → assignments use `person`
- **Constraint:** At least one target must be set (`assignment_must_have_target` CheckConstraint)
- Use `assignment.target` property to get the target regardless of type
- Use `assignment.target_name` property to get the display name

**Constraints:**
- `unique_person_assignment` - Unique person per effort (when person is set)
- `unique_election_voter_assignment` - Unique election voter per effort (when election_voter is set)
- `assignment_must_have_target` - CheckConstraint ensuring person OR election_voter is set

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

# Campaign (Organization) CRUD
/campaigns/                              → org_campaign_list
/campaigns/create/                       → org_campaign_create
/campaigns/<uuid:pk>/                    → org_campaign_detail
/campaigns/<uuid:pk>/edit/               → org_campaign_edit
/campaigns/<uuid:pk>/delete/             → org_campaign_delete

# Drive (ContactEffort) CRUD
/drives/                                 → campaign_list (drive list)
/drives/create/                          → campaign_create (drive create)
/drives/<uuid:pk>/                       → campaign_detail (drive detail)
/drives/<uuid:pk>/edit/                  → campaign_edit (drive edit)
/drives/<uuid:pk>/delete/                → campaign_delete (drive delete)
/drives/<uuid:pk>/assignments/           → assignment_list
/drives/<uuid:pk>/assignments/add/       → assignment_add
/drives/<uuid:pk>/assignments/remove/    → assignment_remove (POST only)
/drives/<uuid:pk>/call/                  → calling_session
/drives/<uuid:pk>/call/next/             → calling_next (HTMX)
/drives/<uuid:pk>/call/log/              → calling_log (HTMX POST)
/drives/<uuid:pk>/call/skip/             → calling_skip (HTMX POST)
/drives/<uuid:pk>/knock/                 → knocking_session
/drives/<uuid:pk>/knock/location/        → knocking_set_location (HTMX POST)
/drives/<uuid:pk>/knock/next/            → knocking_next (HTMX)
/drives/<uuid:pk>/knock/log/             → knocking_log (HTMX POST)
/drives/<uuid:pk>/knock/skip/            → knocking_skip (HTMX POST)

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
/elections/<uuid:pk>/drives/             → election_campaigns (drives for election)
/elections/<uuid:pk>/dates/add/          → election_date_add
/elections/<uuid:pk>/dates/<uuid>/delete/→ election_date_delete
/elections/<uuid:pk>/candidates/         → candidate_list
/elections/<uuid:pk>/candidates/add/     → candidate_add

/candidates/<uuid:pk>/                   → candidate_detail
/candidates/<uuid:pk>/edit/              → candidate_edit
/candidates/<uuid:pk>/delete/            → candidate_delete

# GeoJSON API Endpoints
/api/drives/<uuid:pk>/locations/         → api_campaign_locations (FeatureCollection)
/api/drives/<uuid:pk>/route/             → api_campaign_route (optimized walking route)
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

### `get_assignment_target_with_details(assignment, effort)`
Fetches the assignment target (Person or ElectionVoter) with all contact-relevant data.
- Handles dual-target polymorphism (Person vs ElectionVoter)
- Returns `(target, target_type)` tuple where `target_type` is `"person"` or `"election_voter"`
- Returns `(None, None)` if target doesn't exist (graceful handling of orphaned records)
- Used by `calling_next`, `calling_log`, `knocking_next`, `knocking_log`

```python
target, target_type = get_assignment_target_with_details(assignment, campaign)
if not target:
    # Handle missing target gracefully
    pass
# target_type is "person" or "election_voter"
```

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

- `CampaignForm` - Create/edit campaigns (organization-level)
- `DriveForm` - Create/edit drives (voter contact efforts, model: ContactEffort)
- `ContactEffortForm` - Alias for DriveForm (backward compatibility)
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
- Green-50 background, navigation bar with Campaigns, Drives, Elections, Offices

**Campaign (Organization) interface (`org_campaigns/`):**
- `campaign_list.html` - List all campaigns with drive counts
- `campaign_detail.html` - Campaign detail with its drives
- `campaign_form.html` - Create/edit campaign
- `campaign_confirm_delete.html` - Delete confirmation

**Drive interface (`campaigns/`):**
- `campaign_list.html` - List all drives with progress
- `campaign_detail.html` - Drive detail with stats and actions
- `campaign_form.html` - Create/edit drive with campaign association
- `calling_session.html` - Phone banking session page
- `knocking_session.html` - Door knocking session page with GPS location picker
- `partials/_person_card.html` - Person display with phone + call outcome form
- `partials/_address_card.html` - Address display with map link + distance + knock outcome form
- `partials/_session_complete.html` - Phone session completion message
- `partials/_knocking_complete.html` - Knocking session completion message
- `partials/_progress_bar.html` - Reusable progress bar (used by both interfaces)

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

### Import TIGER/Line Shapefiles (`import_tiger_shapefile.py`)

Import Census Bureau district boundaries for election coverage visualization and voter filtering.

**Prerequisites:**
```bash
# Install GIS dependencies
uv sync --extra geo
```

**Download shapefiles:**
1. Visit https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
2. Select year and layer type (Counties, Congressional Districts, State Legislative Districts, etc.)
3. Download state-specific or nationwide .zip file
4. Extract to a local directory (e.g., `data/`)

**Import examples:**

```bash
# Import Georgia counties
uv run python manage.py import_tiger_shapefile \
    data/tl_2024_13_county/tl_2024_13_county.shp \
    --district-type county \
    --state GA \
    --effective-date 2024-01-01

# Import congressional districts (nationwide file)
uv run python manage.py import_tiger_shapefile \
    data/tl_2024_us_cd118/tl_2024_us_cd118.shp \
    --district-type congressional \
    --effective-date 2024-01-01

# Import state legislative districts
uv run python manage.py import_tiger_shapefile \
    data/tl_2024_13_sldl/tl_2024_13_sldl.shp \
    --district-type state_house \
    --state GA \
    --effective-date 2024-01-01

# Dry run to preview without saving
uv run python manage.py import_tiger_shapefile \
    data/tl_2024_13_vtd/tl_2024_13_vtd.shp \
    --district-type precinct \
    --state GA \
    --dry-run

# Update existing boundaries with new vintage
uv run python manage.py import_tiger_shapefile \
    data/tl_2025_13_county/tl_2025_13_county.shp \
    --district-type county \
    --state GA \
    --effective-date 2025-01-01 \
    --update-existing
```

**Command options:**
- `--district-type` (required): Type of district (county, congressional, state_house, state_senate, city, precinct, school_district)
- `--state`: Two-letter state code (e.g., GA, CA) - extracted from GEOID if not provided
- `--identifier-field`: Shapefile attribute for district ID (default: GEOID)
- `--name-field`: Shapefile attribute for district name (default: NAME)
- `--county-field`: Shapefile attribute for county name (optional)
- `--effective-date`: Date boundaries took effect (YYYY-MM-DD format)
- `--source`: Data source description (default: "Census TIGER/Line")
- `--dry-run`: Validate without saving to database
- `--update-existing`: Update geometries if district already exists
- `--verbose`: Show detailed progress for each feature

**Functionality:**
- Reads ESRI shapefiles using GeoPandas
- Transforms CRS to EPSG:4326 (WGS84) automatically
- Converts Polygon to MultiPolygon for Django GIS compatibility
- Uses natural key (district_type, state, identifier) for matching
- Reports progress every 50 features
- Stops after 10 errors with detailed error messages
- Atomic transactions per feature

**Linking Elections to Districts:**

After importing districts, link them to elections via Django admin:

1. Navigate to **Elections** in Django admin
2. Open an election record
3. Scroll to **Geographic Coverage** section
4. Select districts using the filter horizontal widget
5. Save

Districts can now be visualized on the election detail page map.

**Using Geographic Filters in Drive Assignments:**

When creating bulk assignments for a drive:

1. Navigate to **Drives** → Select drive → **Assignments** → **Add Assignments**
2. Use the **Geographic Filters** section:
   - **District**: Select a district to only assign voters within that boundary
   - **Radius**: Enter distance in miles and click "Pick on Map" to set center point
3. Combine with party/likelihood filters for targeted outreach
4. Set assignment limit and submit

**Note:** Geographic filtering requires voters to have geocoded locations (see Geocoding section).

### URL-Based District Import (Django Admin)

For convenient browser-based imports without downloading files locally, use the Django admin interface to import shapefiles directly from Census Bureau URLs.

**Access:**
1. Navigate to Django Admin → **District Import Jobs**
2. Click **Add District Import Job**

**Step-by-Step Workflow:**

1. **Configure Import:**
   - **Download URL**: Paste census.gov zip file URL (e.g., `https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip`)
   - **District Type**: Select type (County, Congressional, State House, etc.)
   - **State**: Enter 2-letter code (e.g., GA) or leave blank to auto-detect from GEOID

2. **Field Mapping** (optional - defaults work for most Census files):
   - **Identifier Field**: Shapefile attribute for district ID (default: GEOID)
   - **Name Field**: Shapefile attribute for district name (default: NAME)
   - **County Field**: Optional county attribute

3. **Metadata** (optional):
   - **Effective Date**: When boundaries took effect (YYYY-MM-DD)
   - **Source**: Data source description (default: "Census TIGER/Line")
   - **Update Existing**: Check to update boundaries if districts already exist

4. **Save** the job (status: Pending)

5. **Trigger Import:**
   - Select the job checkbox in the list view
   - From "Actions" dropdown, choose **"Trigger import for selected jobs"**
   - Click **Go**

6. **Monitor Progress:**
   - Refresh the job detail page to see status updates:
     - Pending → Downloading → Processing → Completed/Failed
   - Progress shows: "X/Y (Z%)" and success rate
   - View errors inline if import encounters issues

**Example Census URLs:**

```
# Counties (nationwide, ~20MB, 3,234 features)
https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip

# Georgia State House Districts (~2MB, 180 features)
https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_13_sldl.zip

# Congressional Districts 118th Congress (~10MB, 436 features)
https://www2.census.gov/geo/tiger/TIGER2024/CD/tl_2024_us_cd118.zip

# Georgia State Senate Districts
https://www2.census.gov/geo/tiger/TIGER2024/SLDU/tl_2024_13_sldu.zip

# Voting Districts/Precincts (Georgia example)
https://www2.census.gov/geo/tiger/TIGER2024/VTD/tl_2024_13_vtd20.zip
```

**Features:**
- **Asynchronous Processing**: Imports run in background via Celery, no browser timeout
- **Progress Tracking**: Real-time status updates in admin interface
- **Error Handling**: Individual feature errors logged for review/retry
- **Concurrent Import Prevention**: Can't start duplicate imports for same district type + state
- **Automatic Cleanup**: Temporary files deleted after import
- **Security**: Only accepts census.gov URLs
- **CRS Transformation**: Automatically converts to EPSG:4326 (WGS84)

**Troubleshooting:**

| Issue | Solution |
|-------|----------|
| "URL must be from census.gov domain" | Only census.gov URLs accepted for security |
| "An import job...is already pending" | Wait for existing import to complete or use CLI tool |
| "No .shp file found in zip" | Verify zip contains shapefile components (.shp, .shx, .dbf, .prj) |
| Import stuck in "Downloading" | Check Celery worker is running: `uv run celery -A example worker -l info` |
| Feature errors logged | Review error inline in admin, check field mappings match shapefile attributes |

**When to Use URL-Based vs. CLI Import:**
- **URL-Based (Admin)**: Convenient for one-time imports, browser-based workflow, progress tracking
- **CLI (`import_tiger_shapefile`)**: Automation scripts, custom field mapping, dry-run validation, verbose logging

## Admin Interface

- `PersonAdmin` with TabularInline for phone/email/address and StackedInline for VoterRecord
- `OfficeAdmin` with election count display
- `ElectionAdmin` with CandidateInline, ElectionDateInline, and geocoding status
  - `trigger_geocoding` action - Start geocoding job for election voters
- `CandidateAdmin` with raw_id_fields for person/election
- `CampaignAdmin` with ContactEffortInline (drives), drive count display
- `ContactEffortAdmin` with assignment inline, campaign/election/candidate fields, and stats
- `ContactAttemptAdmin` with raw_id_fields for person lookup
- `GeocodingJobAdmin` with progress display, success rate, and retry action
- `DistrictAdmin` with boundary management
- `DistrictImportJobAdmin` with URL validation, progress tracking, and async import trigger
  - `trigger_import` action - Queue Celery tasks for selected pending jobs
  - Inline display of import errors with feature details
  - Color-coded success rate display (green ≥90%, orange ≥70%, red <70%)
  - Concurrent import prevention for same district type + state
- `DistrictImportErrorAdmin` for viewing individual import errors

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

Tests are located in `civicpulse/tests.py`.

**Test Classes:**
- `AssignmentAddViewTests` - Tests for bulk assignment (Person vs ElectionVoter)
- `CandidateDetailTests` - Tests for candidate view with null/missing person
- `CallingSessionTests` - Tests for phone banking with dual-target support
- `KnockingSessionTests` - Tests for door knocking with dual-target support
- `AssignmentListTests` - Tests for assignment list display
- `GetAssignmentTargetHelperTests` - Tests for helper function

**Running tests:**
```bash
uv run python manage.py test
```

**Note:** Tests require PostgreSQL/PostGIS to run. SpatiaLite in-memory databases have a known trigger issue (`ISO_metadata_reference_row_id_value_insert`) that prevents test database creation. For local development, use PostgreSQL for testing or skip tests until a PostGIS environment is available.

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
