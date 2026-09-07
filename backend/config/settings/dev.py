"""Settings for local development and self-hosted evaluation."""

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import SECRET_KEY

DEBUG = True

if not SECRET_KEY:
    SECRET_KEY = "insecure-development-key-do-not-use-in-production"
