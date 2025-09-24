"""
Django settings for scrobblarr project.

Generated for Django 4.2+ with configuration for Last.fm scrobble analytics.
"""

from pathlib import Path
from decouple import config
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-here-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_extensions',
    'django_q',
    'django_filters',
    'core',
    'music',
    'stats',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityMiddleware',
    'core.middleware.LoggingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ErrorHandlingMiddleware',
]

ROOT_URLCONF = 'scrobblarr.urls'

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

WSGI_APPLICATION = 'scrobblarr.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = config('TIMEZONE', default='UTC')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}


# Django-Q configuration
Q_CLUSTER = {
    'name': 'scrobblarr',
    'workers': 2,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'redis': None,  # Use database broker
}


# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {module} {funcName}:{lineno} [{process:d}:{thread:d}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
            'datefmt': '%H:%M:%S',
        },
        'json': {
            'format': '{{"timestamp": "{asctime}", "level": "{levelname}", "logger": "{name}", "module": "{module}", "function": "{funcName}", "line": {lineno}, "process": {process}, "thread": {thread}, "message": "{message}"}}',
            'style': '{',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
        'error': {
            'format': '{levelname} {asctime} {name} {module} {funcName}:{lineno} [{process:d}:{thread:d}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'console_prod': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_false'],
        },
        'file_info': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'scrobblarr.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'scrobblarr_error.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'error',
        },
        'file_json': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'scrobblarr.json',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 3,
            'formatter': 'json',
        },
        'import_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'import.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'api_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'api.log',
            'maxBytes': 20 * 1024 * 1024,  # 20MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'console_prod', 'file_info'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file_error', 'console', 'console_prod'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_error', 'console', 'console_prod'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['null'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'music': {
            'handlers': ['console', 'console_prod', 'file_info', 'file_error'],
            'level': config('MUSIC_LOG_LEVEL', default='DEBUG'),
            'propagate': False,
        },
        'music.import': {
            'handlers': ['console', 'console_prod', 'import_file', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'stats': {
            'handlers': ['console', 'console_prod', 'file_info', 'file_error'],
            'level': config('STATS_LOG_LEVEL', default='DEBUG'),
            'propagate': False,
        },
        'stats.api': {
            'handlers': ['api_file', 'file_error'],
            'level': 'INFO',
            'propagate': True,
        },
        'core': {
            'handlers': ['console', 'console_prod', 'file_info', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'scrobblarr': {
            'handlers': ['console', 'console_prod', 'file_info', 'file_error', 'file_json'],
            'level': 'INFO',
            'propagate': False,
        },
        'django_q': {
            'handlers': ['console', 'console_prod', 'file_info', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console', 'console_prod', 'file_error'],
    },
}


# Last.fm API configuration
LASTFM_API_KEY = config('LASTFM_API_KEY', default='')
LASTFM_API_SECRET = config('LASTFM_API_SECRET', default='')
SYNC_FREQUENCY = config('SYNC_FREQUENCY', default='daily')


# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)