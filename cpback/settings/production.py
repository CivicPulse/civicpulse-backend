"""
Production settings for cpback project.
"""

import environ

from .base import *

env = environ.Env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = False

# Production allowed hosts - should be set via environment variable
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=[])

# Security settings for production
SECURE_SSL_REDIRECT: bool = env("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS: int = env("SECURE_HSTS_SECONDS", default=31536000)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = env(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
)
SECURE_HSTS_PRELOAD: bool = env("SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_BROWSER_XSS_FILTER: bool = True
SECURE_PROXY_SSL_HEADER: tuple = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS: str = "DENY"
SECURE_REFERRER_POLICY: str = "strict-origin-when-cross-origin"

# Additional security headers
SECURE_CROSS_ORIGIN_OPENER_POLICY: str = "same-origin"
SECURE_PERMISSIONS_POLICY: dict = {
    "accelerometer": [],
    "camera": [],
    "geolocation": [],
    "microphone": [],
    "payment": [],
}

# Session security - Override base settings for production
SESSION_COOKIE_SECURE: bool = True
SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_AGE: int = 3600  # 1 hour (overrides base 30 min)
SESSION_COOKIE_SAMESITE: str = "Strict"  # Stricter than base "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE: bool = False  # Keep session in production
SESSION_SAVE_EVERY_REQUEST: bool = True  # Update session on every request
CSRF_COOKIE_SECURE: bool = True
CSRF_COOKIE_HTTPONLY: bool = True
CSRF_COOKIE_SAMESITE: str = "Strict"

# Email configuration for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@civicpulse.com")

# Production logging - more restrictive
LOGGING["handlers"]["file"]["level"] = "WARNING"
LOGGING["handlers"]["console"]["level"] = "ERROR"
LOGGING["loggers"]["civicpulse"]["level"] = "INFO"
LOGGING["root"]["level"] = "WARNING"

# Additional production-specific apps
INSTALLED_APPS += [
    # Add production-specific apps here
    # 'storages',  # For cloud storage
]

# Cloud storage settings (if using AWS S3, Google Cloud Storage, etc.)
# Uncomment and configure as needed
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'
# AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
# AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
# AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='')
# AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='us-east-1')

# Cache configuration for production
# Use Redis for caching and rate limiting in production
# Falls back to database cache if Redis is unavailable
try:
    import redis

    # Test Redis connection
    redis_url = env("REDIS_URL", default="redis://127.0.0.1:6379/1")
    redis_client = redis.from_url(redis_url)
    redis_client.ping()  # Test connection

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "TIMEOUT": 300,  # 5 minutes default timeout
            "OPTIONS": {},  # Simplified - Django's Redis backend has fewer options
            "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="civicpulse_prod"),
            "VERSION": 1,
        },
        # Separate cache for sessions to improve performance
        "sessions": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/2"),
            "TIMEOUT": 3600,  # 1 hour for sessions
            "OPTIONS": {},  # Simplified - Django's Redis backend has fewer options
            "KEY_PREFIX": (
                env("CACHE_KEY_PREFIX", default="civicpulse_prod") + "_sessions"
            ),
        },
    }

    # Use Redis for session storage in production
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "sessions"

except (ImportError, redis.ConnectionError, redis.TimeoutError) as e:
    import warnings

    warnings.warn(
        f"Redis connection failed ({e}), falling back to database cache. "
        "This may impact performance in distributed deployments.",
        RuntimeWarning,
        stacklevel=2,
    )

    # Fallback to database cache if Redis is not available
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "civicpulse_cache_table",
            "TIMEOUT": 300,
            "OPTIONS": {
                "MAX_ENTRIES": 10000,
                "CULL_FREQUENCY": 4,
            },
            "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="civicpulse_prod"),
            "VERSION": 1,
        }
    }

    # Use database sessions as fallback
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Django-Axes Configuration for Production with Redis
# Override base settings to ensure axes uses Redis cache
AXES_CACHE = "default"  # Use the default cache (Redis) for axes
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 0.5  # 30 minutes lockout (in hours)
AXES_LOCKOUT_TEMPLATE = "registration/account_locked.html"
AXES_LOCK_OUT_AT_FAILURE = True
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ADMIN = True
AXES_VERBOSE = True
AXES_LOCKOUT_CALLABLE = None  # Use default lockout behavior
AXES_USERNAME_FORM_FIELD = "username"
AXES_PASSWORD_FORM_FIELD = "password"

# Enhanced rate limiting for production
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]  # Lock by both IP and username
AXES_LOCKOUT_URL = None  # Redirect to default lockout template
AXES_NEVER_LOCKOUT_WHITELIST = env("AXES_WHITELIST_IPS", default="", cast=list)
AXES_NEVER_LOCKOUT_GET = True  # Never lockout GET requests

# Use database handler as fallback
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
