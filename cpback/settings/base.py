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
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, ''),
)

# Read environment variables from .env file
environ.Env.read_env(BASE_DIR / '.env')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = env('DEBUG')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = env('SECRET_KEY')

# Validate SECRET_KEY is not empty or insecure default
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set!")

if SECRET_KEY.startswith('django-insecure-'):
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
            stacklevel=2
        )

ALLOWED_HOSTS: list[str] = env('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS: list[str] = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS: list[str] = [
    # Add third-party apps here
]

LOCAL_APPS: list[str] = [
    'civicpulse',
]

INSTALLED_APPS: list[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE: list[str] = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF: str = 'cpback.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION: str = 'cpback.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Use DATABASE_URL if available, otherwise fallback to SQLite
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation'
        '.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE: str = 'en-us'
TIME_ZONE: str = 'UTC'
USE_I18N: bool = True
USE_TZ: bool = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL: str = '/static/'
STATIC_ROOT: Path = env('STATIC_ROOT', default=BASE_DIR / 'staticfiles', cast=Path)
STATICFILES_DIRS: list[Path] = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL: str = '/media/'
MEDIA_ROOT: Path = env('MEDIA_ROOT', default=BASE_DIR / 'media', cast=Path)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD: str = 'django.db.models.BigAutoField'

# Ensure logs directory exists
logs_dir = BASE_DIR / 'logs'
os.makedirs(logs_dir, exist_ok=True)

# Logging Configuration
LOGGING: dict[str, Any] = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            'format': '{{"level": "{levelname}", "time": "{asctime}", '
            '"module": "{module}", "message": "{message}"}}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': logs_dir / 'django.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': logs_dir / 'django_errors.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'civicpulse': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
