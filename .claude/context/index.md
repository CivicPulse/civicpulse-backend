# CivicPulse Backend - AI Agent Context

Quick reference for AI agents working on this Django-based civic outreach platform.

## What This Project Does

CivicPulse is a contact management, election tracking, and phone banking platform for civic organizations. Users can:
1. Import voter data from CSV files
2. Track elections with offices, candidates, and key dates
3. Create outreach campaigns with scripts (optionally linked to elections/candidates)
4. Assign voters to campaigns with filtering (party, likelihood)
5. Run calling sessions with HTMX-powered UI
6. Track contact outcomes and progress

## Key Technologies

| Component | Technology | Version |
|-----------|------------|---------|
| Backend | Django | 6.0+ |
| Python | uv-managed | 3.13+ |
| Frontend | Tailwind CSS | 4.1+ |
| Interactivity | HTMX | 2.0.4 |
| Components | Flowbite | CDN |
| Database | SQLite/PostgreSQL | - |

## Critical Files

| Purpose | File |
|---------|------|
| Models | `civicpulse/models.py` |
| Views | `civicpulse/views.py` |
| URLs | `civicpulse/urls.py` |
| Forms | `civicpulse/forms.py` |
| Admin | `civicpulse/admin.py` |
| Settings | `example/settings.py` |
| Base Template | `civicpulse/templates/_base.html` |
| CSV Import | `civicpulse/management/commands/import_voters.py` |

## Data Model Summary

```
Person (UUID PK)
├── phone_numbers (PhoneNumber[])
├── emails (Email[])
├── addresses (Address[])
├── voter_record (VoterRecord, OneToOne)
├── contact_attempts (ContactAttempt[])
├── effort_assignments (EffortAssignment[])
└── candidacies (Candidate[])

Office (UUID PK) - Elected position (Mayor, City Council, etc.)
├── level: federal/state/county/city/school_district/other
├── jurisdiction: city, county, state fields
└── elections (Election[])

Election (UUID PK) - Race for an office
├── office (FK → Office)
├── election_type: general/primary/special/runoff
├── year, status (upcoming/active/completed/certified)
├── parent_election (FK → self, for primary→general links)
├── Key dates: qualifying, registration, early voting, election day, certification
├── candidates (Candidate[])
├── additional_dates (ElectionDate[])
└── contact_efforts (ContactEffort[])

Candidate (UUID PK) - Person running in election
├── person (FK → Person)
├── election (FK → Election)
├── party_affiliation, is_incumbent, status
└── contact_efforts (ContactEffort[])

ElectionDate (UUID PK) - Additional dates (debates, forums, etc.)
├── election (FK → Election)
└── date_type: candidate_forum/debate/filing_deadline/campaign_event/other

ContactEffort (Campaign)
├── election (FK → Election, optional)
├── candidate (FK → Candidate, optional)
├── assignments (EffortAssignment[])
└── attempts (ContactAttempt[])

EffortAssignment (Person-to-Campaign link with locking)
├── status: pending → in_progress → completed
├── locked_by: User (prevents concurrent access)
└── locked_at: timestamp (stale after 10 min)

ContactAttempt (Call/Text log)
├── outcome: spoke_with, no_answer, busy, etc.
└── Terminal outcomes: spoke_with, refused, wrong_number
```

## URL Patterns

**Campaigns:**
- `/campaigns/` - List campaigns
- `/campaigns/<uuid>/` - Campaign dashboard
- `/campaigns/<uuid>/call/` - Calling session (HTMX)
- `/campaigns/<uuid>/call/next/` - Get next person (HTMX)
- `/campaigns/<uuid>/call/log/` - Log outcome (HTMX POST)
- `/campaigns/<uuid>/assignments/` - Manage assignments

**Elections:**
- `/offices/` - List offices
- `/offices/<uuid>/` - Office detail
- `/elections/` - List elections
- `/elections/<uuid>/` - Election detail (dates, candidates)
- `/elections/<uuid>/candidates/` - Manage candidates
- `/elections/<uuid>/campaigns/` - Associated contact campaigns
- `/candidates/<uuid>/` - Candidate detail

**Other:**
- `/` - Home
- `/admin/` - Django admin

## Common Development Tasks

### Run Development Server
```bash
uv run python manage.py runserver
```

### Run Tailwind Watcher (separate terminal)
```bash
npx @tailwindcss/cli -i static/src/input.css -o static/src/output.css --watch
```

### Format/Lint Code
```bash
uv run black .
uv run ruff check .
```

### Import Voter Data
```bash
uv run python manage.py import_voters path/to/file.csv
```

## Concurrent Caller Pattern

The calling workflow uses row-level locking to support multiple simultaneous callers:

```python
# In views.py: get_next_assignment()
with transaction.atomic():
    assignment = EffortAssignment.objects.select_for_update(skip_locked=True)
        .filter(effort=effort, status="pending")
        .first()
```

Key points:
- `skip_locked=True` allows concurrent callers
- Stale locks (>10 min) are auto-released
- Terminal outcomes mark assignment completed

## HTMX Flow

1. `calling_session.html` loads with `hx-trigger="load"`
2. `calling_next` returns `_person_card.html` partial
3. User submits outcome via `hx-post` to `calling_log`
4. `calling_log` logs attempt, returns next person card

## Forms

- `CampaignForm` - Create/edit campaigns
- `ContactAttemptForm` - Log call outcomes (7 choices)
- `AssignmentFilterForm` - Filter by party, likelihood, has_phone
- `OfficeForm` - Create/edit elected offices
- `ElectionForm` - Create/edit elections with all date fields
- `CandidateForm` - Add/edit candidates for elections
- `ElectionDateForm` - Add additional dates to elections

## Admin Access

All model editing via Django admin at `/admin/`.

**Person admin** includes inline editing for:
- Phone numbers, emails, addresses (TabularInline)
- Voter record (StackedInline)

**Election admin** includes inline editing for:
- Candidates (TabularInline)
- Additional dates (TabularInline)

**ContactEffort admin** includes:
- Assignment inline and optional election/candidate fields

## Testing

```bash
uv run python manage.py test
```

Note: Tests not yet implemented in `civicpulse/tests.py`.

## Important Constraints

1. **Always use `uv`** for Python commands (never system Python)
2. **All views require login** via `@login_required`
3. **All models use UUID primary keys**
4. **Tailwind must be compiled** before CSS changes appear
5. **Conventional Commits** for git messages
