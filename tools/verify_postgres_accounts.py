"""Verify real PostgreSQL registration/login with a rolled-back temporary account."""
import json
import os
import secrets
import sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.test import Client, override_settings
from django.urls import reverse


def main():
    assert connection.vendor == 'postgresql', 'Verification must use actual PostgreSQL'
    User = get_user_model()
    before = User.objects.count()
    backups = sorted((ROOT / '.database-backups').glob('*/migration_report.json'))
    if backups:
        backup = backups[-1].parent
        settings.DATABASES['original_backup'] = {**settings.DATABASES['default'],
            'ENGINE': 'django.db.backends.sqlite3', 'NAME': backup / 'db.sqlite3',
            'OPTIONS': {}, 'USER': '', 'PASSWORD': '', 'HOST': '', 'PORT': ''}
        snapshots = []
        for alias in ('original_backup', 'default'):
            stream = StringIO()
            call_command('dumpdata', database=alias, natural_foreign=True,
                         exclude=['contenttypes', 'auth.permission'], stdout=stream, verbosity=0)
            snapshots.append(sorted(json.loads(stream.getvalue()), key=lambda row: (row['model'], str(row['pk']))))
        # Existing users can sign in while verification runs; never overwrite
        # their newer last-login timestamp with a historical backup value.
        for snapshot in snapshots:
            for row in snapshot:
                if row['model'] == 'accounts.userprofile':
                    row['fields'].pop('last_login', None)
        if snapshots[0] != snapshots[1]:
            differences = []
            original_rows = {(row['model'], str(row['pk'])): row['fields'] for row in snapshots[0]}
            copied_rows = {(row['model'], str(row['pk'])): row['fields'] for row in snapshots[1]}
            for key in original_rows.keys() | copied_rows.keys():
                first, second = original_rows.get(key, {}), copied_rows.get(key, {})
                changed = [name for name in first.keys() | second.keys() if first.get(name) != second.get(name)]
                if changed:
                    differences.append({'model': key[0], 'pk': key[1], 'changed_field_names': changed})
            print(json.dumps(differences[:15], indent=2))
            raise AssertionError('Record contents differ from the original backup')
    token = secrets.token_hex(6)
    with transaction.atomic(), override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
        client = Client()
        username, password = 'migration-check-' + token, secrets.token_urlsafe(30)
        email = token + '@example.invalid'
        response = client.post(reverse('register'), {'username': username, 'email': email,
                               'password': password, 'password2': password})
        assert response.status_code == 302 and response.url == reverse('login')
        assert '_auth_user_id' not in client.session
        assert User.objects.get(username=username).check_password(password)
        login = client.post(reverse('login'), {'email': email, 'password': password})
        assert login.status_code == 302 and login.url == reverse('dashboard')
        assert '_auth_user_id' in client.session
        transaction.set_rollback(True)
    assert User.objects.count() == before
    report = {'engine': connection.vendor, 'accounts_preserved': before,
              'registration_redirects_to_login': True, 'login_succeeded': True,
              'all_exported_record_contents_match_original_backup': bool(backups),
              'comparison_excludes': ['accounts.userprofile.last_login (normal sign-in activity)'],
              'temporary_account_rolled_back': True}
    (ROOT / '.postgres-migration/verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
