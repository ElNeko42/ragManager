"""Admin registration for the owner account."""

from django.contrib import admin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at", "last_login")
    readonly_fields = ("user_id", "password", "created_at", "last_login")
