# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Architecture

**Project structure:**
- `example/` - Django project configuration (settings.py, urls.py, wsgi.py)
- `civicpulse/` - Main Django app (views, models, templates)
- `static/src/` - Tailwind CSS source (input.css → output.css)

**Frontend stack:**
- Tailwind CSS with django-compressor for bundling
- Flowbite components (loaded from CDN)
- Templates use `{% compress css %}` for CSS processing

**Authentication:**
- Django's built-in auth with `@login_required` on views
- Login/logout at `/login/` and `/logout/`
- Users created via Django admin only

**Database:**
- SQLite by default (db.sqlite3)
- PostgreSQL supported via .env configuration
- All models use UUID primary keys

## Data Models

**Person** (`civicpulse/models.py`) - Core contact record:
- Fields: first_name, last_name, middle_name, nickname, organization, job_title, voter_id
- `voter_id` - unique external voter file ID (used for CSV import matching)
- Optional OneToOne link to Django User via `user` field
- Related models use ForeignKey with CASCADE delete

**Related models** (all linked to Person):
- `PhoneNumber` - number, type (mobile/home/work/other), is_primary
- `Email` - email, type (personal/work/other), is_primary
- `Address` - street_address, city, state (2-char), zip_code, type (home/work/mailing), is_primary
- `VoterRecord` - OneToOne with Person, stores voter-specific data

**VoterRecord** (`civicpulse/models.py`) - Voter-specific data:
- Demographics: registered_party, gender, age, ethnicity, marital_status, spoken_language, military_status, changed_party
- Location: latitude, longitude, apartment_type, street_number_parity
- Voting scores: likelihood_general, likelihood_primary, likelihood_combined (stored as strings like "77%")
- Voting history: voted_general_2024/2022/2020/2018, voted_primary_2024/2022/2020/2018 (booleans)
- Household: household_party, mailing_household_size, mailing_family_id, mailing_household_count, mailing_household_party

**Access patterns:**
```python
person.phone_numbers.all()  # Get all phone numbers
person.emails.filter(is_primary=True)  # Get primary email
person.addresses.filter(type='home')  # Get home addresses
person.voter_record  # Get voter record (OneToOne)
Person.objects.filter(voter_record__registered_party='Democratic')  # Filter by voter data
```

**Admin:** Person admin includes TabularInline for phone/email/address and StackedInline for VoterRecord

## Contact Logging

**ContactEffort** - Represents an outreach campaign (e.g., "2024 GOTV Phone Bank"):
- Fields: name, description, script (caller talking points), is_active
- Created by a User, tracks created_at/updated_at

**ContactAttempt** - Logs each contact attempt within an effort:
- Links to ContactEffort (CASCADE) and Person (CASCADE)
- `contact_type`: "call" (Phone Call) or "text" (Text Message)
- `outcome` choices:
  - `no_answer` - No Answer (retry eligible)
  - `busy` - Busy Signal (retry eligible)
  - `left_voicemail` - Left Voicemail (retry eligible)
  - `callback_requested` - Callback Requested (retry eligible)
  - `wrong_number` - Wrong Number (terminal)
  - `spoke_with` - Spoke With Person (terminal)
  - `refused` - Refused/Do Not Contact (terminal)
- `notes` for conversation details, `callback_time` for scheduling
- `phone_number_used` tracks which number was called/texted

**EffortAssignment** - Pre-assigns persons to campaigns with locking:
- Links to ContactEffort and Person (unique_together)
- `status`: pending → in_progress → completed
- `locked_by`/`locked_at`: Prevents concurrent callers from getting same person
- Stale locks (>10 min) are automatically released

**Terminal outcomes** (defined in `ContactAttempt.TERMINAL_OUTCOMES`):
Person should not be contacted again within the same effort after: spoke_with, refused, wrong_number

**Database indexes:** effort+status, locked_by+locked_at for efficient querying

## Campaign UI

**URL Routes** (`/campaigns/`):
- `/campaigns/` - List all campaigns with progress stats
- `/campaigns/create/` - Create new campaign
- `/campaigns/<uuid>/` - Campaign detail/dashboard
- `/campaigns/<uuid>/edit/` - Edit campaign
- `/campaigns/<uuid>/delete/` - Delete with confirmation
- `/campaigns/<uuid>/assignments/` - Manage assigned persons
- `/campaigns/<uuid>/assignments/add/` - Bulk assign with filters
- `/campaigns/<uuid>/call/` - Start calling session (HTMX-powered)

**Calling Workflow (HTMX)**:
The calling session uses HTMX for smooth transitions without full page reloads:
- `calling_next` - Locks and returns next person card
- `calling_log` - Logs outcome, releases lock, returns next person
- `calling_skip` - Releases lock without logging, returns next person

**Concurrent Caller Support**:
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
        assignment.save()
```

**Templates** (`civicpulse/templates/campaigns/`):
- `campaign_list.html` - Campaign grid with progress bars
- `campaign_detail.html` - Dashboard with stats and actions
- `campaign_form.html` - Create/edit form
- `calling_session.html` - Main calling interface
- `partials/_person_card.html` - Person details + outcome form (HTMX partial)
- `partials/_session_complete.html` - All done message

**Forms** (`civicpulse/forms.py`):
- `CampaignForm` - Create/edit campaigns
- `ContactAttemptForm` - Log call outcomes
- `AssignmentFilterForm` - Filter persons for bulk assignment (party, likelihood, has_phone)

## Management Commands

**Import voters from CSV:**
```bash
uv run python manage.py import_voters path/to/file.csv           # Run import
uv run python manage.py import_voters path/to/file.csv --dry-run # Validate only
```

The import command:
- Matches/creates Person records by voter_id
- Creates/updates VoterRecord, Address (home + mailing), PhoneNumber
- Reports progress every 100 rows
- Stops after 10 errors with row-level details
- Uses atomic transactions per row
