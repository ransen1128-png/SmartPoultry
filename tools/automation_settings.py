"""Isolated settings used by the numbered browser test runner."""

from core.settings import *  # noqa: F401,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
