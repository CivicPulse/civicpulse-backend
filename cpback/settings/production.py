"""
Production settings for cpback project.
"""


import environ

from .base import *

env = environ.Env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = False

# Production allowed hosts - should be set via environment variable
ALLOWED_HOSTS: list[str] = env('ALLOWED_HOSTS')

# Security settings for production
SECURE_SSL_REDIRECT: bool = env('SECURE_SSL_REDIRECT', default=True)
SECURE_HSTS_SECONDS: int = env('SECURE_HSTS_SECONDS', default=31536000)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = env(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True
)
SECURE_HSTS_PRELOAD: bool = env('SECURE_HSTS_PRELOAD', default=True)
SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_BROWSER_XSS_FILTER: bool = True
SECURE_PROXY_SSL_HEADER: tuple = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS: str = 'DENY'
SECURE_REFERRER_POLICY: str = 'strict-origin-when-cross-origin'

# Additional security headers
SECURE_CROSS_ORIGIN_OPENER_POLICY: str = 'same-origin'
SECURE_PERMISSIONS_POLICY: dict = {
    'accelerometer': [],
    'camera': [],
    'geolocation': [],
    'microphone': [],
    'payment': [],
}

# Session security
SESSION_COOKIE_SECURE: bool = True
SESSION_COOKIE_HTTPONLY: bool = True
SESSION_COOKIE_AGE: int = 3600  # 1 hour
SESSION_COOKIE_SAMESITE: str = 'Strict'
CSRF_COOKIE_SECURE: bool = True
CSRF_COOKIE_HTTPONLY: bool = True
CSRF_COOKIE_SAMESITE: str = 'Strict'

# Email configuration for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@civicpulse.com')

# Production logging - more restrictive
LOGGING['handlers']['file']['level'] = 'WARNING'
LOGGING['handlers']['console']['level'] = 'ERROR'
LOGGING['loggers']['civicpulse']['level'] = 'INFO'
LOGGING['root']['level'] = 'WARNING'

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
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
    }
}
