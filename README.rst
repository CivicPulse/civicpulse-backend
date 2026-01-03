=================
django-civicpulse
=================

.. image:: https://img.shields.io/pypi/v/django-civicpulse.svg
    :target: https://pypi.org/project/django-civicpulse/

.. image:: https://img.shields.io/pypi/pyversions/django-civicpulse.svg
    :target: https://pypi.org/project/django-civicpulse/

.. image:: https://img.shields.io/badge/Django-5.0%20%7C%206.0-green.svg
    :target: https://www.djangoproject.com/

Contact management, election tracking, and campaign orchestration
for civic organizations and nonprofits.

Features
--------

* **Contact Management**: Person records with phone, email, addresses, and voter data
* **Election Tracking**: Offices, elections, candidates with comprehensive date tracking
* **Campaign Orchestration**: Phone banking and door knocking workflows
* **Concurrent Users**: Row-level locking supports multiple simultaneous users
* **HTMX Integration**: Smooth, single-page workflow experience
* **Voter Import**: Bulk import from voter file CSVs

Quick Start
-----------

1. Install the package::

    pip install django-civicpulse

   Or with uv::

    uv add django-civicpulse

2. Add ``civicpulse`` to ``INSTALLED_APPS``::

    INSTALLED_APPS = [
        ...
        "civicpulse",
    ]

3. Include the URLs in your project's ``urls.py``::

    from django.urls import include, path

    urlpatterns = [
        path("admin/", admin.site.urls),
        path("accounts/", include("django.contrib.auth.urls")),
        path("", include("civicpulse.urls")),
    ]

4. Run migrations::

    python manage.py migrate civicpulse

5. Create a superuser and start the server::

    python manage.py createsuperuser
    python manage.py runserver

Configuration
-------------

Add optional settings to your Django settings::

    CIVICPULSE = {
        # Site branding
        "SITE_NAME": "My Organization",

        # Lock timeout for concurrent users (minutes)
        "LOCK_TIMEOUT_MINUTES": 10,

        # Enable django-compressor for CSS (requires django-compressor)
        "USE_COMPRESSOR": False,

        # CDN URLs (override to self-host)
        "CDN_FLOWBITE": "https://cdn.jsdelivr.net/npm/flowbite@4.0.1/dist/flowbite.min.js",
        "CDN_HTMX": "https://unpkg.com/htmx.org@2.0.4",
    }

Optional: CSS Compression
~~~~~~~~~~~~~~~~~~~~~~~~~

For CSS compression, install with the compressor extra::

    pip install django-civicpulse[compressor]

Then add to ``INSTALLED_APPS``::

    INSTALLED_APPS = [
        ...
        "compressor",
        "civicpulse",
    ]

And configure::

    CIVICPULSE = {
        "USE_COMPRESSOR": True,
    }

    STATICFILES_FINDERS = (
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        "compressor.finders.CompressorFinder",
    )

Template Customization
----------------------

Override any template by creating your own in your project's templates directory::

    your_project/
    └── templates/
        └── civicpulse/
            └── base.html  # Your custom base template

The base template provides these blocks for customization:

* ``title`` - Page title
* ``extra_head`` - Additional head content
* ``styles`` - CSS includes
* ``navigation`` - Navigation bar
* ``content`` - Main content area
* ``scripts`` - JavaScript includes

Data Models
-----------

CivicPulse provides 12 interconnected models:

* **Person** - Core contact record with voter_id for CSV matching
* **PhoneNumber, Email, Address** - Contact information
* **VoterRecord** - Comprehensive voter data (demographics, voting history)
* **Office** - Elected positions (Mayor, City Council, etc.)
* **Election** - Election races with dates and status tracking
* **ElectionDate** - Additional dates (debates, forums, deadlines)
* **Candidate** - Links persons to elections
* **ContactEffort** - Campaign definitions with scripts
* **ContactAttempt** - Individual contact logs (calls, knocks)
* **EffortAssignment** - Assigns persons to campaigns with locking

Management Commands
-------------------

Import voters from CSV::

    python manage.py import_voters path/to/voters.csv
    python manage.py import_voters path/to/voters.csv --dry-run  # Validate only

Requirements
------------

* Python 3.11+
* Django 5.0+

Documentation
-------------

Full documentation at https://django-civicpulse.readthedocs.io

License
-------

AGPL-3.0 - See LICENSE file for details.

This means if you modify CivicPulse and deploy it as a service,
you must make your source code available.

Contributing
------------

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.
