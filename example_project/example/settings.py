"""
Django settings for the CivicPulse example project.

This demonstrates how to configure a Django project to use django-civicpulse.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-example-only-change-in-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",  # GeoDjango for spatial database support
    # Optional: uncomment for CSS compression
    # "compressor",
    # Celery results backend
    "django_celery_results",
    "civicpulse",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "example.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "example.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
# GeoDjango supports: PostGIS (production) and SpatiaLite (development)


def _detect_spatialite():
    """
    Try to detect if SpatiaLite SQLite extension is available.
    Note: libspatialite.so is NOT the same as mod_spatialite.so
    We specifically need the loadable SQLite extension (mod_spatialite).
    """
    import ctypes
    # Only check for mod_spatialite, not libspatialite
    library_names = [
        "mod_spatialite.so",
        "mod_spatialite",
        "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
    ]
    for name in library_names:
        try:
            ctypes.cdll.LoadLibrary(name)
            return True
        except OSError:
            continue
    return False


# Determine database engine based on environment
_db_engine = os.environ.get("DB_ENGINE", "")

if not _db_engine:
    # Auto-detect: use SpatiaLite if available, otherwise standard SQLite
    if _detect_spatialite():
        _db_engine = "django.contrib.gis.db.backends.spatialite"
    else:
        # Fall back to standard SQLite (spatial features limited)
        _db_engine = "django.db.backends.sqlite3"

DATABASES = {
    "default": {
        "ENGINE": _db_engine,
        "NAME": os.environ.get("DB_NAME", BASE_DIR / "db.sqlite3"),
    }
}

# Add PostGIS connection details if using PostgreSQL
if "postgis" in _db_engine:
    DATABASES["default"].update({
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    })

# SpatiaLite library path (required for SpatiaLite backend)
# Ubuntu/Debian: /usr/lib/x86_64-linux-gnu/mod_spatialite.so
# macOS: /opt/homebrew/lib/mod_spatialite.dylib
if os.environ.get("SPATIALITE_LIBRARY_PATH"):
    SPATIALITE_LIBRARY_PATH = os.environ["SPATIALITE_LIBRARY_PATH"]

# GDAL library path (if not in standard system paths)
if os.environ.get("GDAL_LIBRARY_PATH"):
    GDAL_LIBRARY_PATH = os.environ["GDAL_LIBRARY_PATH"]


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Optional: Uncomment for CSS compression (requires django-compressor)
# COMPRESS_ROOT = BASE_DIR / "static"
# COMPRESS_ENABLED = True
# STATICFILES_FINDERS = (
#     "django.contrib.staticfiles.finders.FileSystemFinder",
#     "django.contrib.staticfiles.finders.AppDirectoriesFinder",
#     "compressor.finders.CompressorFinder",
# )


# Authentication
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "civicpulse:index"
LOGOUT_REDIRECT_URL = "login"


# CivicPulse Configuration
# See https://django-civicpulse.readthedocs.io for all options

CIVICPULSE = {
    "SITE_NAME": "CivicPulse Demo",
    "LOCK_TIMEOUT_MINUTES": 10,
    "USE_COMPRESSOR": False,
    "INCLUDE_DEFAULT_NAV": True,
}


# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Celery Configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"  # Store results in Django database
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max per task

# Redis transport options for production
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 43200,  # 12 hours for long imports
}


# Media files (uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Maximum upload size (100MB for large voter files)
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600


# =============================================================================
# GIS and Geocoding Configuration
# =============================================================================

# Redis cache for geocoding results (30-day TTL)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
    }
}

# Geocoding service configuration
CIVICPULSE_GEOCODING = {
    # API Keys (use environment variables in production)
    "OPENCAGE_API_KEY": os.environ.get("OPENCAGE_API_KEY", ""),
    # Rate limiting
    "REQUESTS_PER_SECOND": 1,  # Conservative default for free tier
    "BATCH_SIZE": 100,  # Records per batch in bulk geocoding
    "BATCH_DELAY_SECONDS": 60,  # Delay between batches
    # Retry settings
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_BASE": 2,  # Exponential backoff: 2^attempt seconds
    # Cache settings
    "CACHE_TIMEOUT_DAYS": 30,
    # Quality thresholds
    "MIN_CONFIDENCE": 0.5,  # Minimum confidence to accept geocoding result
}

# OSRM Routing Service Configuration
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
# For production, use self-hosted: http://localhost:5000
