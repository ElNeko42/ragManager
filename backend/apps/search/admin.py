"""Admin registration for the record of agent queries."""

from django.contrib import admin

from apps.search.models import AgentQuery


@admin.register(AgentQuery)
class AgentQueryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "agent_name", "source", "query", "result_count", "duration_ms")
    list_filter = ("source", "failed", "agent")
    search_fields = ("query", "agent_name")
    readonly_fields = tuple(field.name for field in AgentQuery._meta.fields)

    def has_add_permission(self, request):
        """Refuse rows typed by hand: this table is a record of what happened."""
        return False
