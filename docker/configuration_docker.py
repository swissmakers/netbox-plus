"""
NetBox configuration for container / Compose deployments.

Loaded when NETBOX_CONFIGURATION=netbox.configuration_docker (set in the image).
All sensitive values should come from environment variables or Docker secrets.
"""
import hashlib
import json
import os

from django.core.exceptions import ImproperlyConfigured


def _split_hosts(value, default='*'):
    raw = os.environ.get(value, default)
    return [h.strip() for h in raw.split(',') if h.strip()]


def _int(name, default):
    return int(os.environ.get(name, str(default)))


def _bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


ALLOWED_HOSTS = _split_hosts('NETBOX_ALLOWED_HOSTS', '*')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('NETBOX_DB_NAME', 'netbox'),
        'USER': os.environ.get('NETBOX_DB_USER', 'netbox'),
        'PASSWORD': os.environ.get('NETBOX_DB_PASSWORD', ''),
        'HOST': os.environ.get('NETBOX_DB_HOST', 'postgres'),
        'PORT': os.environ.get('NETBOX_DB_PORT', ''),
        'CONN_MAX_AGE': _int('NETBOX_DB_CONN_MAX_AGE', 300),
    }
}

_redis_host = os.environ.get('NETBOX_REDIS_HOST', 'redis')
_redis_port = _int('NETBOX_REDIS_PORT', 6379)
_redis_pw = os.environ.get('NETBOX_REDIS_PASSWORD', '')
_redis_ssl = _bool('NETBOX_REDIS_SSL', False)

REDIS = {
    'tasks': {
        'HOST': _redis_host,
        'PORT': _redis_port,
        'USERNAME': os.environ.get('NETBOX_REDIS_USERNAME', ''),
        'PASSWORD': _redis_pw,
        'DATABASE': _int('NETBOX_REDIS_DATABASE_TASKS', 0),
        'SSL': _redis_ssl,
    },
    'caching': {
        'HOST': _redis_host,
        'PORT': _redis_port,
        'USERNAME': os.environ.get('NETBOX_REDIS_USERNAME', ''),
        'PASSWORD': _redis_pw,
        'DATABASE': _int('NETBOX_REDIS_DATABASE_CACHE', 1),
        'SSL': _redis_ssl,
    },
}

SECRET_KEY = os.environ.get('NETBOX_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('NETBOX_SECRET_KEY must be set (at least 50 characters recommended).')

# v2 API tokens require at least one pepper (50+ chars). Optional explicit env overrides Compose default.
_peppers_json = os.environ.get('NETBOX_API_TOKEN_PEPPERS_JSON', '').strip()
if _peppers_json:
    _raw_peppers = json.loads(_peppers_json)
    API_TOKEN_PEPPERS = {int(k): v for k, v in _raw_peppers.items()}
else:
    _pepper1 = os.environ.get('NETBOX_API_TOKEN_PEPPER_1', '').strip()
    if len(_pepper1) >= 50:
        API_TOKEN_PEPPERS = {1: _pepper1}
    else:
        # Deterministic from SECRET_KEY so restarts keep the same pepper without extra env vars.
        API_TOKEN_PEPPERS = {
            1: hashlib.sha256((SECRET_KEY + ':netbox-docker-api-token-pepper').encode()).hexdigest(),
        }

DEBUG = _bool('NETBOX_DEBUG', False)
DEVELOPER = _bool('NETBOX_DEVELOPER', False)

# Compose web runs Gunicorn only; serve collectstatic output unless you add a reverse proxy for STATIC_URL.
SERVE_STATIC_IN_APP = _bool('NETBOX_SERVE_STATIC', True)

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('NETBOX_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

EMAIL = {
    'SERVER': os.environ.get('NETBOX_EMAIL_SERVER', 'localhost'),
    'PORT': _int('NETBOX_EMAIL_PORT', 25),
    'USERNAME': os.environ.get('NETBOX_EMAIL_USERNAME', ''),
    'PASSWORD': os.environ.get('NETBOX_EMAIL_PASSWORD', ''),
    'USE_SSL': _bool('NETBOX_EMAIL_USE_SSL', False),
    'USE_TLS': _bool('NETBOX_EMAIL_USE_TLS', False),
    'TIMEOUT': _int('NETBOX_EMAIL_TIMEOUT', 10),
    'FROM_EMAIL': os.environ.get('NETBOX_EMAIL_FROM', ''),
}

METRICS_ENABLED = _bool('NETBOX_METRICS_ENABLED', False)

# Avoid outbound release/census calls from disposable containers unless opted in.
RELEASE_CHECK_URL = os.environ.get('NETBOX_RELEASE_CHECK_URL', None)
CENSUS_REPORTING_ENABLED = _bool('NETBOX_CENSUS_REPORTING', False)
