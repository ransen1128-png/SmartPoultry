"""Read-only inspection; connection credentials are never printed."""
from pathlib import Path
import sqlite3
import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
config = dotenv_values(ROOT / '.env')
credentials = dict(user=config.get('DB_USER'), password=config.get('DB_PASSWORD'),
                   host=config.get('DB_HOST', 'localhost'), port=config.get('DB_PORT', '5432'), connect_timeout=5)
with psycopg2.connect(dbname='postgres', **credentials) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT datname FROM pg_database WHERE datistemplate=false')
        print('PostgreSQL databases:', [row[0] for row in cursor.fetchall()])
try:
    with psycopg2.connect(dbname=config.get('DB_NAME'), **credentials) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s', ['public'])
            tables = [row[0] for row in cursor.fetchall()]
            print('Configured database public tables:', tables)
            if 'accounts_userprofile' in tables:
                cursor.execute('SELECT count(*) FROM accounts_userprofile')
                print('PostgreSQL account count:', cursor.fetchone()[0])
except psycopg2.OperationalError:
    print('Configured database could not be opened.')
with sqlite3.connect(f'file:{(ROOT / "db.sqlite3").as_posix()}?mode=ro', uri=True) as source:
    print('SQLite account count:', source.execute('SELECT count(*) FROM accounts_userprofile').fetchone()[0])
