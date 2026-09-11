"""Settings shared by every deployment target."""

import os
from pathlib import Path

from corsheaders.defaults import default_headers as default_cors_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None):
    """Read an environment variable as text.

    Treats an empty value as absent so that a placeholder left blank in
    .env.example falls back to the given default.
    """
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_int(name, default=None):
    """Read an environment variable as an integer."""
    value = env(name)
    return default if value is None else int(value)


def env_list(name, default=None):
    """Read an environment variable as a comma separated list of strings."""
    value = env(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

PUBLIC_HOST = env("PUBLIC_HOST")

if PUBLIC_HOST:
    ALLOWED_HOSTS.append(PUBLIC_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{PUBLIC_HOST}")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "apps.accounts",
    "apps.agents",
    "apps.drive",
    "apps.access",
    "apps.ingestion",
    "apps.search",
    "apps.mcp",
    "apps.oauth",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestSizeLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "ragmanager"),
        "USER": env("POSTGRES_USER", "ragmanager"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", "postgres"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
# The MCP endpoint and the authorization flow answer any origin regardless;
# see config.cors. These are the headers that transport sends and reads.
CORS_ALLOW_HEADERS = [
    *default_cors_headers,
    "mcp-protocol-version",
    "mcp-session-id",
    "last-event-id",
]
CORS_EXPOSE_HEADERS = ["WWW-Authenticate", "Mcp-Session-Id", "Mcp-Protocol-Version"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.agents.authentication.AgentTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "account": "10/min",
        "search": env("SEARCH_THROTTLE_RATE", "60/min"),
        "oauth-register": env("OAUTH_REGISTER_THROTTLE_RATE", "10/hour"),
        "oauth-token": env("OAUTH_TOKEN_THROTTLE_RATE", "60/min"),
    },
    "NUM_PROXIES": env_int("TRUSTED_PROXY_COUNT", 1 if PUBLIC_HOST else 0),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.Pagination",
}

PAGE_SIZE = env_int("PAGE_SIZE", 100)
MAX_PAGE_SIZE = env_int("MAX_PAGE_SIZE", 500)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", "redis://redis:6379/1"),
    }
}

CELERY_BROKER_URL = env("REDIS_URL", "redis://redis:6379/0")
CELERY_TASK_IGNORE_RESULT = True
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CHUNK_WORDS = env_int("CHUNK_WORDS", 200)
CHUNK_OVERLAP_WORDS = env_int("CHUNK_OVERLAP_WORDS", 40)

INGESTION_SOFT_TIME_LIMIT_SECONDS = env_int("INGESTION_SOFT_TIME_LIMIT_SECONDS", 900)
INGESTION_TIME_LIMIT_SECONDS = env_int("INGESTION_TIME_LIMIT_SECONDS", 960)
INGESTION_MAX_RETRIES = env_int("INGESTION_MAX_RETRIES", 5)
INGESTION_RETRY_BACKOFF_SECONDS = env_int("INGESTION_RETRY_BACKOFF_SECONDS", 30)
INGESTION_RETRY_MAX_BACKOFF_SECONDS = env_int("INGESTION_RETRY_MAX_BACKOFF_SECONDS", 900)

QDRANT_URL = env("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = env("QDRANT_API_KEY")

S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", "http://minio:9000")
S3_REGION = env("S3_REGION", "us-east-1")
S3_BUCKET = env("S3_BUCKET", "ragmanager")
S3_ACCESS_KEY_ID = env("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = env("S3_SECRET_ACCESS_KEY")

MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 536870912)

RAGMANAGER_VERSION = "0.1.0"

MCP_PATH = "/mcp/"

# The authorization flow that lets a connector obtain a token through a
# browser instead of the owner copying one. An access token is short lived
# because a connector can always renew it; a code is shorter still, since it
# travels through a redirect.
OAUTH_CODE_LIFETIME_SECONDS = env_int("OAUTH_CODE_LIFETIME_SECONDS", 120)
OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS = env_int("OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS", 3600)
OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS = env_int("OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS", 2592000)
OAUTH_TOKEN_PREFIX = "rmo_"

EMBEDDING_API_KEY = env("EMBEDDING_API_KEY")

# Encrypts the provider credentials the panel stores. Its own variable rather
# than the Django secret, which is rotated to invalidate sessions and must not
# take every stored credential with it.
CREDENTIALS_ENCRYPTION_KEY = env("CREDENTIALS_ENCRYPTION_KEY")

# The endpoints offered in the panel as a starting point. A file rather than a
# table of vendors in the code, so an operator can ship their own list.
PROVIDER_CATALOGUE = env("PROVIDER_CATALOGUE", str(BASE_DIR / "apps" / "ingestion" / "providers.json"))

OCR_LANGUAGES = env("OCR_LANGUAGES", "eng")
VISION_BASE_URL = env("VISION_BASE_URL")
VISION_API_KEY = env("VISION_API_KEY")
VISION_MODEL = env("VISION_MODEL")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
