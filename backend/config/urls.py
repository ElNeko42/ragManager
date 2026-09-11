"""Root URL routing for the ragManager API."""

from django.contrib import admin
from django.urls import include, path

from apps.oauth import views as oauth_views
from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path(
        ".well-known/oauth-protected-resource",
        oauth_views.protected_resource,
        name="oauth-protected-resource",
    ),
    path(
        ".well-known/oauth-protected-resource/mcp",
        oauth_views.protected_resource,
        name="oauth-protected-resource-mcp",
    ),
    path(
        ".well-known/oauth-authorization-server",
        oauth_views.authorization_server,
        name="oauth-authorization-server",
    ),
    path("oauth/", include("apps.oauth.urls")),
    path("api/", include("config.api_urls")),
    # Answered at both spellings. The resource identifier this server
    # publishes carries no trailing slash, and a client using exactly the
    # address it was given must not be met with a redirect: a redirect on a
    # POST is where a body goes missing and a connector reports that there is
    # no server here at all.
    path("mcp/", include("apps.mcp.urls")),
    path("mcp", include("apps.mcp.urls")),
    path("admin/", admin.site.urls),
]
