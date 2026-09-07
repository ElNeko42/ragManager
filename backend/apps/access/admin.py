"""Admin registration for agent access rules."""

from django.contrib import admin

from apps.access.models import Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("agent", "effect", "folder", "document", "created_at")
    list_filter = ("agent", "effect")
    readonly_fields = ("permission_id", "created_at")
