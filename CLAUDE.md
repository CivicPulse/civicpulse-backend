# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CivicPulse is a Django-based contact management, election tracking, and campaign orchestration platform designed for civic organizations and nonprofits. It provides voter contact data management, election and candidate tracking, campaign creation, and HTMX-powered phone banking/texting workflows with concurrent caller support using database row-level locking.

**Tech Stack:**
- Backend: Django 6.0+, Python 3.13+
- Frontend: Tailwind CSS 4.1+, Flowbite components, HTMX 2.0.4
- Database: SQLite (dev), PostgreSQL (prod-capable)
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

## Project Structure

```
civicpulse-backend/
├── civicpulse/                 # Main Django app
│   ├── models.py              # Core data models (12 models)
│   ├── views.py               # View functions (30 views, ~700 LOC)
│   ├── urls.py                # URL routing
│   ├── forms.py               # Django forms (7 forms)
│   ├── admin.py               # Django admin config
│   ├── management/
│   │   └── commands/
│   │       └── import_voters.py  # CSV bulk import command
│   └── templates/
│       ├── _base.html         # Base template with nav & CDN libs
│       ├── index.html         # Home page
│       ├── registration/
│       │   └── login.html     # Login page
│       ├── campaigns/
│       │   ├── campaign_list.html
│       │   ├── campaign_detail.html
│       │   ├── campaign_form.html
│       │   ├── campaign_confirm_delete.html
│       │   ├── calling_session.html
│       │   ├── assignment_list.html
│       │   ├── assignment_add.html
│       │   └── partials/
│       │       ├── _person_card.html       # Person display + outcome form
│       │       ├── _progress_bar.html      # Reusable progress bar
│       │       └── _session_complete.html  # All done message
│       └── elections/
│           ├── office_list.html
│           ├── office_detail.html
│           ├── office_form.html
│           ├── office_confirm_delete.html
│           ├── election_list.html
│           ├── election_detail.html
│           ├── election_form.html
│           ├── election_confirm_delete.html
│           ├── election_campaigns.html
│           ├── election_date_form.html
│           ├── candidate_list.html
│           ├── candidate_detail.html
│           ├── candidate_form.html
│           └── candidate_confirm_delete.html
├── example/                   # Django project config
│   ├── settings.py           # Django settings
│   ├── urls.py               # Root URL config
│   └── wsgi.py               # WSGI app entry
├── static/
│   └── src/
│       ├── input.css         # Tailwind source
│       └── output.css        # Compiled Tailwind
├── pyproject.toml            # uv/Python config
├── package.json              # Node dependencies
└── db.sqlite3                # Dev database
```

## Architecture

**Frontend stack:**
- Tailwind CSS with django-compressor for bundling
- Flowbite components (loaded from CDN)
- HTMX 2.0.4 for seamless partial page updates
- Templates use `{% compress css %}` for CSS processing

**Authentication:**
- Django's built-in auth with `@login_required` on all views
- Login/logout at `/login/` and `/logout/`
- Users created via Django admin only
- `LOGIN_URL = "login"`, `LOGIN_REDIRECT_URL = "/"`

**Database:**
- SQLite by default (db.sqlite3)
- PostgreSQL supported via .env configuration
- All models use UUID primary keys

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

### VoterRecord (`civicpulse/models.py:134-195`)
OneToOne with Person, stores comprehensive voter data.

**Demographics:**
- `registered_party`, `gender`, `age`, `ethnicity`, `marital_status`
- `spoken_language`, `military_status`, `changed_party`

**Location:**
- `latitude`, `longitude` (DecimalField, 6 decimal places)
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

### ContactAttempt (`civicpulse/models.py:223-277`)
Logs each contact attempt within a campaign.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person)
- `contact_type`: "call" or "text"
- `outcome` choices:
  - `no_answer` - No Answer (retry eligible)
  - `busy` - Busy Signal (retry eligible)
  - `left_voicemail` - Left Voicemail (retry eligible)
  - `callback_requested` - Callback Requested (retry eligible)
  - `wrong_number` - Wrong Number (terminal)
  - `spoke_with` - Spoke With Person (terminal)
  - `refused` - Refused/Do Not Contact (terminal)
- `notes`, `callback_time`, `phone_number_used`

**Terminal outcomes:** `TERMINAL_OUTCOMES = [spoke_with, refused, wrong_number]`

### EffortAssignment (`civicpulse/models.py:279-318`)
Pre-assigns persons to campaigns with locking support.

- `effort` (ForeignKey → ContactEffort)
- `person` (ForeignKey → Person)
- `status`: pending → in_progress → completed
- `locked_by` / `locked_at`: Prevents concurrent callers from getting same person
- `unique_together = ["effort", "person"]`

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
```

## View Helper Functions

Located in `civicpulse/views.py`:

### `get_next_assignment(effort, user)` (lines 241-269)
Core lock acquisition logic for concurrent callers.
- Releases stale locks (>10 min old)
- Uses `select_for_update(skip_locked=True)` for row-level locking
- Returns locked assignment or None

### `get_person_with_details(person_id, effort)` (lines 272-288)
Efficiently fetches person with all calling-relevant data.
- Uses select_related + prefetch_related
- Prefetches last 5 attempts for this effort

### `get_session_stats(effort)` (lines 291-304)
Calculates campaign progress stats.
- Returns: total, pending, in_progress, completed, percentage, remaining

## Concurrent Caller Support

Uses `select_for_update(skip_locked=True)` for row-level locking:
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
- Skips locked rows, allows multiple concurrent callers
- Atomic transaction ensures only one caller gets each person
- 10-minute stale lock timeout auto-releases abandoned locks

## HTMX Calling Workflow

1. User loads `/campaigns/<uuid>/call/` → `calling_session.html`
2. HTMX triggers `hx-get="/call/next/"` on load
3. `calling_next` returns person card partial with form
4. User selects outcome and submits via `hx-post="/call/log/"`
5. `calling_log` processes outcome, releases lock, calls `calling_next`
6. `calling_next` returns next person card or completion message

## Forms (`civicpulse/forms.py`)

- `CampaignForm` - Create/edit campaigns
- `ContactAttemptForm` - Log call outcomes with radio buttons
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

**Calling interface partials (`campaigns/partials/`):**
- `_person_card.html` - Person display + outcome form (231 lines)
- `_progress_bar.html` - Reusable progress bar
- `_session_complete.html` - All done message

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
- `ElectionAdmin` with CandidateInline and ElectionDateInline
- `CandidateAdmin` with raw_id_fields for person/election
- `ContactEffortAdmin` with assignment inline, election/candidate fields, and stats
- `ContactAttemptAdmin` with raw_id_fields for person lookup

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
- `SECRET_KEY` - Django secret key
- `DEBUG` - Set to False
- `ALLOWED_HOSTS` - Comma-separated hostnames
- `DATABASE_URL` - PostgreSQL connection string (optional)
