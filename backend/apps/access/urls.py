"""Routes for the agent access rules."""

from django.urls import path

from apps.access import views

urlpatterns = [
    path("", views.PermissionListCreateView.as_view(), name="permission-list"),
    path(
        "effective/<uuid:agent_id>/",
        views.EffectiveAccessView.as_view(),
        name="permission-effective",
    ),
    path(
        "<uuid:permission_id>/", views.PermissionDetailView.as_view(), name="permission-detail"
    ),
]
