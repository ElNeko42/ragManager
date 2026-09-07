"""Routes for the agent access rules."""

from django.urls import path

from apps.access import views

urlpatterns = [
    path("", views.PermissionListCreateView.as_view(), name="permission-list"),
    path(
        "<uuid:permission_id>/", views.PermissionDetailView.as_view(), name="permission-detail"
    ),
]
