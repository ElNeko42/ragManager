"""Application registry entry for the OAuth authorization server."""

from django.apps import AppConfig


class OauthConfig(AppConfig):
    name = "apps.oauth"
    verbose_name = "OAuth authorization"
