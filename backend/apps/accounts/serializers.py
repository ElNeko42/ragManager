"""Serializers for the owner session endpoints."""

from rest_framework import serializers

from apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        """Normalise the submitted address to match how it was stored."""
        return value.lower()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("user_id", "email")
        read_only_fields = fields
