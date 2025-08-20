"""
Base Django settings for cpback project.
Common settings shared across all environments.
"""

import os
from pathlib import Path
from typing import Any

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# Initialize environment variables
env: environ.Env = environ.Env(
    # Set casting and defaults for environment variables
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, ""),
    PERSON_IMPORT_MAX_FILE_SIZE=(int, 10 * 1024 * 1024),  # 10MB default
)

# Read environment variables from .env file
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = env("DEBUG")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = env("SECRET_KEY")

# Validate SECRET_KEY is not empty or insecure default
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set!")

if SECRET_KEY.startswith("django-insecure-"):
    if not DEBUG:
        raise ValueError(
            "Insecure SECRET_KEY detected in production! "
            "Generate a secure one using: "
            "python -c 'from django.core.management.utils import "
            "get_random_secret_key; print(get_random_secret_key())'"
        )
    else:
        import warnings

        warnings.warn(
            "Using insecure SECRET_KEY in development. "
            "This is only acceptable for development/testing. "
            "Generate a secure one for production!",
            UserWarning,
            stacklevel=2,
        )

ALLOWED_HOSTS: list[str] = env("ALLOWED_HOSTS")

# Application definition
DJANGO_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS: list[str] = [
    "axes",  # Account lockout protection
]

LOCAL_APPS: list[str] = [
    "civicpulse",
]

INSTALLED_APPS: list[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Current user middleware - stores user in thread-local storage for audit trail
    "civicpulse.middleware.current_user.CurrentUserMiddleware",
    "axes.middleware.AxesMiddleware",  # Account lockout middleware
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Audit middleware - tracks all HTTP requests and user actions
    "civicpulse.middleware.audit.AuditMiddleware",
]

ROOT_URLCONF: str = "cpback.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION: str = "cpback.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Use DATABASE_URL if available, otherwise fallback to SQLite
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

# Enhanced Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
        "OPTIONS": {
            "user_attributes": ("username", "first_name", "last_name", "email"),
            "max_similarity": 0.7,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 12,  # Require at least 12 characters
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    # Add custom password validators for enhanced security
    {
        "NAME": "civicpulse.validators.PasswordComplexityValidator",
    },
    {
        "NAME": "civicpulse.validators.PasswordHistoryValidator",
        "OPTIONS": {
            "password_history_count": 5,  # Prevent reuse of last 5 passwords
        },
    },
    {
        "NAME": "civicpulse.validators.PasswordStrengthValidator",
        "OPTIONS": {
            "min_entropy": 50,  # Minimum entropy for password strength
        },
    },
    {
        "NAME": "civicpulse.validators.CommonPasswordPatternValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_TZ: bool = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL: str = "/static/"
STATIC_ROOT: Path = env("STATIC_ROOT", default=BASE_DIR / "staticfiles", cast=Path)
STATICFILES_DIRS: list[Path] = [
    BASE_DIR / "static",
]

# Media files
MEDIA_URL: str = "/media/"
MEDIA_ROOT: Path = env("MEDIA_ROOT", default=BASE_DIR / "media", cast=Path)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = "civicpulse.User"

# Authentication Configuration
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

# Session Configuration
SESSION_COOKIE_AGE = 1800  # 30 minutes default session timeout
SESSION_COOKIE_SECURE = not DEBUG  # Use secure cookies in production
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookies
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Expire session when browser closes
SESSION_SAVE_EVERY_REQUEST = True  # Update session on every request

# CSRF Configuration
CSRF_COOKIE_SECURE = not DEBUG  # Use secure CSRF cookies in production
CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access to CSRF tokens
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = True  # Store CSRF tokens in sessions instead of cookies

# Security Headers
SECURE_BROWSER_XSS_FILTER = True  # Enable XSS filtering
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME sniffing
X_FRAME_OPTIONS = "DENY"  # Prevent clickjacking
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Rate Limiting Configuration
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts before lockout
LOGIN_LOCKOUT_DURATION = 300  # Lockout duration in seconds (5 minutes)
MAX_REGISTRATION_ATTEMPTS = 3  # Maximum registration attempts per IP
REGISTRATION_LOCKOUT_DURATION = 600  # Registration lockout duration (10 minutes)

# Cache Configuration for Rate Limiting
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "civicpulse-cache",
        "TIMEOUT": 300,  # 5 minutes default timeout
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
            "CULL_FREQUENCY": 3,
        },
    }
}

# Email Configuration
# Default email settings (can be overridden in environment-specific settings)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = env("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@civicpulse.com")
SERVER_EMAIL = env("SERVER_EMAIL", default="admin@civicpulse.com")

# Admin notification settings
ADMINS = [
    ("CivicPulse Admin", env("ADMIN_EMAIL", default="admin@civicpulse.com")),
]
MANAGERS = ADMINS

# Account Security Settings
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # Require email verification
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "username_email"  # Allow login with username or email

# Security Monitoring Threshold Configuration
# These settings control when security alerts are triggered
SECURITY_FAILED_LOGIN_THRESHOLD = env(
    "SECURITY_FAILED_LOGIN_THRESHOLD", default=5, cast=int
)  # failures per time window
SECURITY_FAILED_LOGIN_WINDOW_HOURS = env(
    "SECURITY_FAILED_LOGIN_WINDOW_HOURS", default=1, cast=int
)  # time window in hours
SECURITY_EXPORT_THRESHOLD = env(
    "SECURITY_EXPORT_THRESHOLD", default=10, cast=int
)  # exports per time window
SECURITY_EXPORT_WINDOW_HOURS = env(
    "SECURITY_EXPORT_WINDOW_HOURS", default=24, cast=int
)  # time window in hours
SECURITY_PRIVILEGE_ESCALATION_WINDOW_HOURS = env(
    "SECURITY_PRIVILEGE_ESCALATION_WINDOW_HOURS", default=24, cast=int
)  # time window in hours

# Ensure logs directory exists
logs_dir = BASE_DIR / "logs"
os.makedirs(logs_dir, exist_ok=True)

# Logging Configuration
LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "json": {
            "format": '{{"level": "{levelname}", "time": "{asctime}", '
            '"module": "{module}", "message": "{message}"}}',
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": logs_dir / "django.log",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": logs_dir / "django_errors.log",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["error_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "civicpulse": {
            "handlers": ["console", "file", "error_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Django-Axes Configuration (Account Lockout Protection)
# https://django-axes.readthedocs.io/en/latest/configuration.html
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 0.5  # 30 minutes lockout (in hours)
AXES_LOCKOUT_TEMPLATE = "registration/account_locked.html"
AXES_LOCK_OUT_AT_FAILURE = True  # Lock out at failure threshold
AXES_RESET_ON_SUCCESS = True  # Reset failure count on successful login
AXES_ENABLE_ADMIN = True  # Enable admin interface for managing lockouts
AXES_VERBOSE = True  # Enable verbose logging

# Authentication Backend Configuration
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",  # AxesBackend should be first
    "django.contrib.auth.backends.ModelBackend",
]

# File Upload Settings
# Maximum file size for person imports (in bytes)
PERSON_IMPORT_MAX_FILE_SIZE: int = env("PERSON_IMPORT_MAX_FILE_SIZE")
