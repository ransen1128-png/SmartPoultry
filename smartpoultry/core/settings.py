"""
Django settings for SMARTPOULTRY project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUNNING_ON_RENDER = bool(os.getenv('RENDER') or os.getenv('RENDER_EXTERNAL_HOSTNAME'))

# Load project environment variables after BASE_DIR is known.
# Keep real environment variables from deployment platforms authoritative.
if not RUNNING_ON_RENDER:
    load_dotenv(BASE_DIR / '.env', override=False)

# SECURITY WARNING: keep the secret key used in production secret!
# The fallback is public (it is in source control): anyone could forge session
# cookies and password-reset tokens with it, so hosted deployments refuse it.
SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
if not SECRET_KEY:
    if RUNNING_ON_RENDER:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('SECRET_KEY must be set in the Render environment.')
    SECRET_KEY = 'django-insecure-dev-key-change-in-production'

RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG_ENV = os.getenv('DEBUG')
DEBUG = False if RUNNING_ON_RENDER else DEBUG_ENV.lower() in ('1', 'true', 'yes', 'on') if DEBUG_ENV is not None else True

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com').split(',')
    if host.strip()
]
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'https://*.onrender.com' if RUNNING_ON_RENDER else '').split(',')
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
    'accounts',
    'flocks',
    'inventory',
    'revenue',
    'expenses',
    'analytics',
    'reports',
    'production',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.PrivatePageCacheMiddleware',
    'core.middleware.FarmActivityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# HTTPS hardening for the hosted site. Render terminates TLS at its proxy and
# forwards the original scheme. Local runs stay on plain HTTP.
if RUNNING_ON_RENDER:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    # Render's internal health probe may not arrive over HTTPS.
    SECURE_REDIRECT_EXEMPT = [r'^__health/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Start HSTS short; raise to a year once HTTPS is confirmed stable.
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '3600'))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

# The estimator runs several CPU models per photo behind one inference slot.
ROOSTER_ESTIMATOR_MAX_PHOTOS = int(os.getenv('ROOSTER_ESTIMATOR_MAX_PHOTOS', '5'))

ROOT_URLCONF = 'core.urls'
LOGIN_URL = 'login'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'smartpoultry' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.admin_notifications.context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# PostgreSQL is explicit locally and mandatory on Render.
from .database import database_settings
DATABASES = {'default': database_settings(os.environ, BASE_DIR)}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'core.password_validation.PasswordComplexityValidator'},
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

# Use HTTPS email delivery: Render's free plan blocks standard SMTP ports.
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'core.email_backend.ResendEmailBackend')
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '').strip()
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '').strip()
EMAIL_TIMEOUT = 10
PASSWORD_RESET_TIMEOUT = 30 * 60
PASSWORD_RESET_METHOD = os.getenv('PASSWORD_RESET_METHOD', 'questions').strip().lower()
# A canonical origin keeps reset links on this deployment, behind Render's proxy.
PASSWORD_RESET_BASE_URL = os.getenv(
    'PASSWORD_RESET_BASE_URL',
    f'https://{RENDER_EXTERNAL_HOSTNAME}' if RENDER_EXTERNAL_HOSTNAME else '',
).strip().rstrip('/')

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'smartpoultry' / 'static']
STORAGES = {
    # Uploads go to the database because Render's disk is cleared on every deploy.
    'default': {'BACKEND': 'core.storage.DatabaseStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
WHITENOISE_USE_FINDERS = True

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.UserProfile'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]
