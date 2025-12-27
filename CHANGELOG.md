# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
