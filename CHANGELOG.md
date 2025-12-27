# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GeoDjango Integration**: Full spatial database support with PostGIS (prod) and SpatiaLite (dev)
- **Spatial Fields**: Added `location` PointField to VoterRecord, ElectionVoter, Address, VoterAddress models
- **District Model**: New model for voting precincts and district boundaries with MultiPolygonField
- **Geocoding Service**: Address-to-coordinates with OpenCage (primary) and Nominatim (fallback)
- **Routing Service**: OSRM integration for optimized walking routes in door knocking
- **Celery Tasks**: Background geocoding tasks with rate limiting and retry logic
- **GeocodingJob/GeocodingError Models**: Track and monitor bulk geocoding operations
- **Interactive Maps**: Leaflet.js integration with route visualization in door knocking
- **GeoJSON API Endpoints**: `/api/campaigns/<pk>/locations/`, `/api/campaigns/<pk>/route/`, `/api/districts/`
- **Spatial View Helpers**: `get_voters_within_radius()`, `get_voters_in_district()`, etc.
- **Admin Enhancements**: Geocoding job management, retry failed addresses action, district admin

### Changed

- **Database Engine**: Updated from SQLite to SpatiaLite for development (GeoDjango spatial extension)
- **Door Knocking**: Now uses GeoDjango `Distance` function for database-level proximity sorting
- **Tech Stack**: Added Leaflet.js for mapping, Celery for background tasks

## [0.1.0] - 2024-12-26

### Added

- Initial release as a reusable Django app
- Contact management with Person, PhoneNumber, Email, Address models
- VoterRecord model for comprehensive voter data
- Election tracking with Office, Election, Candidate, ElectionDate models
- Campaign orchestration with ContactEffort, ContactAttempt, EffortAssignment models
- Phone banking workflow with HTMX-powered interface
- Door knocking workflow with GPS-based address sorting
- Concurrent user support with database row-level locking
- Voter CSV import management command
- Tailwind CSS styling with Flowbite components
- Django admin integration

### Changed

- Restructured as installable package with src/ layout
- Made django-compressor an optional dependency
- Added configurable settings via CIVICPULSE dict
- Namespaced templates under civicpulse/
- Namespaced static files under civicpulse/

[Unreleased]: https://github.com/civicpulse/django-civicpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/civicpulse/django-civicpulse/releases/tag/v0.1.0
