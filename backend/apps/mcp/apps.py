"""Application entry for the Model Context Protocol endpoint."""

from django.apps import AppConfig


class McpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mcp"
    verbose_name = "MCP server"
