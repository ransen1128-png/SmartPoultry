from pathlib import Path
from unittest import TestCase

from django.core.exceptions import ImproperlyConfigured
from core.database import database_settings


class DatabaseConfigurationTests(TestCase):
    def test_desktop_explicit_postgres_uses_loopback_without_a_hidden_flag(self):
        database = database_settings({'USE_POSTGRES': 'True', 'DB_HOST': '127.0.0.1',
                                      'DB_NAME': 'desktop', 'DB_USER': 'app', 'DB_PASSWORD': 'test'}, Path('/app'))
        self.assertEqual(database['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(database['NAME'], 'desktop')

    def test_render_never_falls_back_to_sqlite(self):
        for env in ({'RENDER': 'true'}, {'RENDER_EXTERNAL_HOSTNAME': 'test.onrender.com', 'USE_POSTGRES': 'False'}):
            with self.assertRaisesRegex(ImproperlyConfigured, 'SQLite fallback is disabled'):
                database_settings(env, Path('/app'))

    def test_url_preserves_escaped_credentials_and_ssl_settings(self):
        database = database_settings({'RENDER': 'true', 'DATABASE_URL':
            'postgresql://app%40user:p%40ss%2Fword@db.example.com:5433/accounts?sslmode=require'}, Path('/app'))
        self.assertEqual(database['USER'], 'app@user')
        self.assertEqual(database['PASSWORD'], 'p@ss/word')
        self.assertEqual(database['PORT'], 5433)
        self.assertEqual(database['OPTIONS']['sslmode'], 'require')

    def test_invalid_database_url_fails_instead_of_resetting_accounts(self):
        for url in ('sqlite:///tmp/db.sqlite3', 'postgresql://localhost/', 'broken'):
            with self.assertRaises(ImproperlyConfigured):
                database_settings({'DATABASE_URL': url}, Path('/app'))

    def test_local_sqlite_remains_available_for_explicit_legacy_export(self):
        self.assertEqual(database_settings({'USE_POSTGRES': 'False'}, Path('/app'))['ENGINE'], 'django.db.backends.sqlite3')
