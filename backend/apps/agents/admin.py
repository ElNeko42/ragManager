"""Admin registration for agents and their tokens."""

from django.contrib import admin

from apps.agents.models import Agent, AgentToken


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    readonly_fields = ("agent_id", "created_at")


@admin.register(AgentToken)
class AgentTokenAdmin(admin.ModelAdmin):
    list_display = ("agent", "token_prefix", "created_at", "expires_at", "revoked_at")
    list_filter = ("agent",)
    readonly_fields = ("token_id", "token_hash", "token_prefix", "created_at")
