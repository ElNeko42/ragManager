"""Settings for local development.

Selecting this module is what turns development mode on: it is the single
switch, so there is no way to end up serving with the debug pages enabled
while believing otherwise.
"""

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import PUBLIC_HOST, SECRET_KEY

DEBUG = True

if not SECRET_KEY:
    SECRET_KEY = "insecure-development-key-do-not-use-in-production"

if PUBLIC_HOST:
    import warnings

    warnings.warn(
        f"Serving {PUBLIC_HOST} with development settings: the debug pages expose "
        "tracebacks and configuration to anyone who can reach that host. Switch "
        "DJANGO_SETTINGS_MODULE to config.settings.prod.",
        stacklevel=2,
    )
