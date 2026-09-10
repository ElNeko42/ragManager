"""Root URL routing for the ragManager API."""

from django.contrib import admin
from django.urls import include, path

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/", include("config.api_urls")),
    path("mcp/", include("apps.mcp.urls")),
    path("admin/", admin.site.urls),
]
