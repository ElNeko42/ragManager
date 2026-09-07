"""Routing of the versionless management API."""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("agents/", include("apps.agents.urls")),
]
