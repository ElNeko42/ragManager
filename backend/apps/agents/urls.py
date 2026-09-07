"""Routes for agent management and token issuing."""

from django.urls import path

from apps.agents import views

urlpatterns = [
    path("me/", views.AgentIdentityView.as_view(), name="agent-identity"),
    path("", views.AgentListCreateView.as_view(), name="agent-list"),
    path("<uuid:agent_id>/", views.AgentDetailView.as_view(), name="agent-detail"),
    path(
        "<uuid:agent_id>/tokens/",
        views.AgentTokenListCreateView.as_view(),
        name="agent-token-list",
    ),
    path(
        "<uuid:agent_id>/tokens/<uuid:token_id>/revoke/",
        views.AgentTokenRevokeView.as_view(),
        name="agent-token-revoke",
    ),
]
