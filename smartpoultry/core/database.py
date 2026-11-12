"""Explicit database selection; hosted deployments must never fall back to SQLite."""
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


def database_settings(environment, base_dir):
    hosted = bool(environment.get('RENDER') or environment.get('RENDER_EXTERNAL_HOSTNAME'))
    url = environment.get('DATABASE_URL', '').strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or not parsed.path.strip('/'):
            raise ImproperlyConfigured('DATABASE_URL must be a PostgreSQL connection URL with a host and database name.')
        options = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        options.setdefault('connect_timeout', 10)
        return {'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(parsed.path.lstrip('/')),
                'USER': unquote(parsed.username or ''), 'PASSWORD': unquote(parsed.password or ''),
                'HOST': parsed.hostname, 'PORT': parsed.port or 5432,
                'OPTIONS': options, 'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True}
    if hosted:
        raise ImproperlyConfigured('Render requires a persistent PostgreSQL DATABASE_URL. SQLite fallback is disabled to protect accounts from being erased on redeploy.')
    if environment.get('USE_POSTGRES', '').lower() in ('true', '1', 'yes', 'on'):
        return {'ENGINE': 'django.db.backends.postgresql', 'NAME': environment.get('DB_NAME', 'smartpoultry'),
                'USER': environment.get('DB_USER', 'postgres'), 'PASSWORD': environment.get('DB_PASSWORD', ''),
                'HOST': environment.get('DB_HOST', '127.0.0.1'), 'PORT': environment.get('DB_PORT', '5432'),
                'OPTIONS': {'connect_timeout': 10}, 'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True}
    return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': base_dir / 'db.sqlite3'}
