"""Serializers for agents and their bearer tokens."""

from django.utils import timezone
from rest_framework import serializers

from apps.agents.models import Agent, AgentToken


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ("agent_id", "name", "created_at")
        read_only_fields = ("agent_id", "created_at")


class AgentTokenSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = AgentToken
        fields = (
            "token_id",
            "token_prefix",
            "created_at",
            "expires_at",
            "revoked_at",
            "is_active",
        )
        read_only_fields = fields

    def get_is_active(self, token):
        """Report whether the token would still authenticate its agent."""
        return token.is_valid()


class TokenRequestSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        """Reject an expiry that has already passed."""
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("The expiry must be in the future")
        return value


class AgentCreateSerializer(TokenRequestSerializer):
    name = serializers.CharField(max_length=100)

    def validate_name(self, value):
        """Reject a name already taken by another agent."""
        if Agent.objects.filter(name=value).exists():
            raise serializers.ValidationError("An agent with this name already exists")
        return value
