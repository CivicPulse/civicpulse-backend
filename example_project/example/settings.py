"""
Django settings for the CivicPulse example project.

This demonstrates how to configure a Django project to use django-civicpulse.

Configuration is loaded from environment variables using python-decouple.
Create a .env file from .env.example for local development.
"""

from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# Core Django Settings (from environment)
# =============================================================================

# SECURITY: Required in production - generate with:
# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-only-change-in-production")

# SECURITY: Defaults to False for safety
DEBUG = config("DEBUG", default=False, cast=bool)

# Comma-separated list: localhost,127.0.0.1,example.com
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# CSRF trusted origins for cross-origin requests (Django 4.0+)
# Format: https://example.com (must include scheme)
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]  # Filter empty strings


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
_db_engine = config("DB_ENGINE", default="")

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
        "NAME": config("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
    }
}

# Add PostGIS connection details if using PostgreSQL
if "postgis" in _db_engine:
    DATABASES["default"].update({
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default=5432, cast=int),
    })

# SpatiaLite library path (required for SpatiaLite backend)
# Ubuntu/Debian: /usr/lib/x86_64-linux-gnu/mod_spatialite.so
# macOS: /opt/homebrew/lib/mod_spatialite.dylib
_spatialite_path = config("SPATIALITE_LIBRARY_PATH", default="")
if _spatialite_path:
    SPATIALITE_LIBRARY_PATH = _spatialite_path

# GDAL library path (if not in standard system paths)
_gdal_path = config("GDAL_LIBRARY_PATH", default="")
if _gdal_path:
    GDAL_LIBRARY_PATH = _gdal_path


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
    "SITE_NAME": config("CIVICPULSE_SITE_NAME", default="CivicPulse"),
    "LOCK_TIMEOUT_MINUTES": config("CIVICPULSE_LOCK_TIMEOUT", default=10, cast=int),
    "USE_COMPRESSOR": config("CIVICPULSE_USE_COMPRESSOR", default=False, cast=bool),
    "INCLUDE_DEFAULT_NAV": config("CIVICPULSE_INCLUDE_NAV", default=True, cast=bool),
    # Routing services (see routing fallback chain in services/routing.py)
    "OSRM_URL": config("OSRM_URL", default=None),
    "OPENROUTESERVICE_API_KEY": config("OPENROUTESERVICE_API_KEY", default=None),
    "OPENCAGE_API_KEY": config("OPENCAGE_API_KEY", default=None),
}


# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
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
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# Geocoding service configuration
CIVICPULSE_GEOCODING = {
    # API Keys (use environment variables in production)
    "OPENCAGE_API_KEY": config("OPENCAGE_API_KEY", default=""),
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


# =============================================================================
# Stripe Connect Configuration
# =============================================================================

CIVICPULSE_STRIPE = {
    # OAuth credentials from Stripe Dashboard -> Connect -> Settings
    "CLIENT_ID": config("STRIPE_CLIENT_ID", default=""),
    "SECRET_KEY": config("STRIPE_SECRET_KEY", default=""),
    # Webhook secret for verifying webhook signatures
    "WEBHOOK_SECRET": config("STRIPE_WEBHOOK_SECRET", default=""),
    # Fernet encryption key for storing OAuth tokens at rest
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    "ENCRYPTION_KEY": config("STRIPE_ENCRYPTION_KEY", default=""),
    # OAuth settings
    "OAUTH_SCOPE": "read_write",  # read_only requires special Stripe approval
    # Sync settings
    "SYNC_BATCH_SIZE": 100,  # Charges per API call
    "SYNC_INTERVAL_HOURS": 6,  # Celery beat schedule
}


# =============================================================================
# Development Logging Configuration
# =============================================================================
# Verbose file logging for AI-assisted debugging. Only active when DEBUG=True.
# Log files rotate every 4 hours to prevent unbounded growth.
# See: https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler

if DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "[{asctime}] [{levelname}] [{name}:{funcName}:{lineno}] {message}",
                "style": "{",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "web_file": {
                "level": "DEBUG",
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": BASE_DIR / "civicpulse-web.dev.log",
                "when": "H",
                "interval": 4,
                "formatter": "verbose",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "web_file"],
                "level": "INFO",
                "propagate": True,
            },
            "civicpulse": {
                "handlers": ["console", "web_file"],
                "level": "DEBUG",
                "propagate": True,
            },
            # Suppress SQL query logging
            "django.db.backends": {
                "level": "WARNING",
                "handlers": ["console", "web_file"],
                "propagate": False,
            },
            # Suppress autoreload file watching
            "django.utils.autoreload": {
                "level": "WARNING",
                "handlers": ["console", "web_file"],
                "propagate": False,
            },
            # Suppress template debug messages
            "django.template": {
                "level": "INFO",
                "handlers": ["console", "web_file"],
                "propagate": False,
            },
        },
    }
