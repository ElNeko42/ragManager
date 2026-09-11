"""Routing of the versionless management API."""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("agents/", include("apps.agents.urls")),
    path("permissions/", include("apps.access.urls")),
    path("search/", include("apps.search.urls")),
    path("providers/", include("apps.ingestion.urls")),
    path("", include("apps.drive.urls")),
]
