"""One-time desktop migration: back up, provision an isolated DB, copy, verify, switch.

Run only with the existing local PostgreSQL Windows administrator's authorization.
No PostgreSQL administrator password is changed. Temporary local bootstrap
authentication is restored before migrations or data loading begin.
"""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / '.database-backups' / stamp
    backup.mkdir(parents=True)
    config = dotenv_values(ROOT / '.env')
    if config.get('USE_POSTGRES', '').lower() in ('true', '1', 'yes'):
        raise RuntimeError('App is already configured for PostgreSQL; refusing to rerun the SQLite migration.')
    source = ROOT / 'db.sqlite3'
    with sqlite3.connect(str(source)) as original, sqlite3.connect(str(backup / 'db.sqlite3')) as saved:
        original.backup(saved)
    shutil.copy2(ROOT / '.env', backup / 'environment.before')
    os.environ.pop('DATABASE_URL', None)
    os.environ['USE_POSTGRES'] = 'False'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
    sys.path.insert(0, str(ROOT / 'smartpoultry'))
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections, transaction
    from django.core.management.color import no_style
    from django.contrib.auth import get_user_model
    models = [model for model in apps.get_models() if model._meta.managed and not model._meta.proxy]
    counts = {model._meta.label_lower: model.objects.using('default').count() for model in models}
    users = {user.pk: user.password for user in get_user_model().objects.using('default').all()}
    fixture = backup / 'data.json'
    call_command('dumpdata', database='default', natural_foreign=True,
                 exclude=['contenttypes', 'auth.permission'], output=str(fixture), verbosity=0)
    role, name = f'smartpoultry_app_{stamp.lower()}', f'smartpoultry_desktop_{stamp.lower()}'
    password = secrets.token_urlsafe(36)
    hba = Path('C:/Program Files/PostgreSQL/18/data/pg_hba.conf')
    original_hba = hba.read_bytes()
    (backup / 'pg_hba.before.conf').write_bytes(original_hba)
    bootstrap = None
    try:
        # Localhost-only bootstrap, limited to postgres maintenance DB/role.
        hba.write_bytes(b'host postgres postgres 127.0.0.1/32 trust\n' + original_hba)
        bootstrap = psycopg2.connect(dbname='postgres', user='postgres', host='127.0.0.1',
                                     port=config.get('DB_PORT', '5432'), connect_timeout=5)
        bootstrap.autocommit = True
    finally:
        hba.write_bytes(original_hba)
    assert hba.read_bytes() == original_hba
    try:
        with bootstrap.cursor() as cursor:
            cursor.execute('SELECT datname FROM pg_database WHERE datistemplate=false')
            existing = [row[0] for row in cursor.fetchall()]
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(role)), [password])
            cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {} ENCODING %s TEMPLATE template0').format(sql.Identifier(name), sql.Identifier(role)), ['UTF8'])
    finally:
        bootstrap.close()
    settings.DATABASES['postgres_migration'] = {**settings.DATABASES['default'],
        'ENGINE': 'django.db.backends.postgresql', 'NAME': name, 'USER': role, 'PASSWORD': password,
        'HOST': '127.0.0.1', 'PORT': config.get('DB_PORT', '5432'), 'OPTIONS': {'connect_timeout': 10}}
    # This alias is exclusively the newly created, empty database.
    call_command('migrate', database='postgres_migration', interactive=False, verbosity=0)
    with transaction.atomic(using='postgres_migration'):
        call_command('loaddata', str(fixture), database='postgres_migration', verbosity=0)
        with connections['postgres_migration'].cursor() as cursor:
            for statement in connections['postgres_migration'].ops.sequence_reset_sql(no_style(), models):
                cursor.execute(statement)
        for model in models:
            label = model._meta.label_lower
            if model.objects.using('postgres_migration').count() != counts[label]:
                raise RuntimeError(f'Count mismatch: {label}. Original configuration remains unchanged.')
        copied = {user.pk: user.password for user in get_user_model().objects.using('postgres_migration').all()}
        if copied != users:
            raise RuntimeError('Password hash verification failed; not switching configuration.')
    # Commit to PostgreSQL before changing the app configuration.
    new_config = {**config, 'USE_POSTGRES': 'True', 'DB_NAME': name, 'DB_USER': role,
                  'DB_PASSWORD': password, 'DB_HOST': '127.0.0.1', 'DB_PORT': config.get('DB_PORT', '5432')}
    new_config.pop('DATABASE_URL', None)
    # JSON quoted strings are valid dotenv double-quoted values.
    text = '\n'.join(f'{key}={json.dumps(str(value))}' for key, value in new_config.items() if value is not None) + '\n'
    temporary = ROOT / '.postgres-migration'
    temporary.mkdir(exist_ok=True)
    pending = temporary / 'environment.pending'
    pending.write_text(text, encoding='utf-8')
    os.replace(pending, ROOT / '.env')
    report = {'status': 'migrated_and_verified', 'database': name, 'role': role,
              'accounts_preserved': len(users), 'model_counts': counts,
              'all_password_hashes_identical': True, 'postgres_auth_configuration_restored': hba.read_bytes() == original_hba,
              'original_sqlite_retained': source.exists(), 'backup': str(backup),
              'preexisting_databases_untouched': existing}
    (backup / 'migration_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != 'model_counts'}, indent=2))


if __name__ == '__main__':
    main()
