from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(
    DEBUG=(bool, False),
    DEFAULT_RANGE_MILES=(float, 500.0),
    DEFAULT_MPG=(float, 10.0),
    DEFAULT_CORRIDOR_MILES=(float, 5.0),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-change-me")
DEBUG = env("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "routing",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = env("DATABASE_URL", default="sqlite:///db.sqlite3")
DATABASES = {"default": environ.Env.db_url_config(DATABASE_URL)}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OSRM_BASE_URL = env('OSRM_BASE_URL', default='https://router.project-osrm.org')
ROUTING_TIMEOUT_SECONDS = env('ROUTING_TIMEOUT_SECONDS', default=10)
NOMINATIM_USER_AGENT = env('NOMINATIM_USER_AGENT', default='spotter-fuel-route-assessment')
DEFAULT_RANGE_MILES = env('DEFAULT_RANGE_MILES', default=500.0)
DEFAULT_MPG = env('DEFAULT_MPG', default=10.0)
DEFAULT_CORRIDOR_MILES = env('DEFAULT_CORRIDOR_MILES', default=5.0)

REDIS_URL = env('REDIS_URL', default='')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'fuel-route-api'}}
if REDIS_URL:
    CACHES = {'default': env.cache_url('REDIS_URL')}
