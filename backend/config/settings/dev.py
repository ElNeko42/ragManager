"""Settings for local development.

Selecting this module is what turns development mode on: it is the single
switch, so no combination of variables serves the debug pages while looking
like production.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import ALLOWED_HOSTS, PUBLIC_HOST, SECRET_KEY

DEBUG = True

if not SECRET_KEY:
    SECRET_KEY = "insecure-development-key-do-not-use-in-production"

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

if PUBLIC_HOST and os.environ.get("ALLOW_PUBLIC_DEBUG", "").lower() not in {"1", "true", "yes"}:
    raise ImproperlyConfigured(
        f"Refusing to serve {PUBLIC_HOST} with development settings: the debug pages "
        "expose tracebacks and configuration to anyone who can reach that host. Use "
        "config.settings.prod, or set ALLOW_PUBLIC_DEBUG=true to accept that risk."
    )
