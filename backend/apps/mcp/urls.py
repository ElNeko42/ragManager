"""Routing of the MCP endpoint."""

from django.urls import path

from apps.mcp import views

urlpatterns = [path("", views.McpView.as_view(), name="mcp")]
