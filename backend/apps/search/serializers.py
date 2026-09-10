"""Serializers for the search endpoint and the record it leaves."""

from rest_framework import serializers

from apps.common.fields import OptionalUUIDField
from apps.search.models import AgentQuery

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


class SearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=4000, trim_whitespace=True)
    limit = serializers.IntegerField(
        required=False, default=DEFAULT_LIMIT, min_value=1, max_value=MAX_LIMIT
    )
    folder = serializers.UUIDField(required=False, allow_null=True)

    def validate_query(self, value):
        """Reject a query with nothing to search for."""
        if not value.strip():
            raise serializers.ValidationError("The query cannot be empty")
        return value


class AgentQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentQuery
        fields = (
            "query_id",
            "agent",
            "agent_name",
            "query",
            "source",
            "folder",
            "limit",
            "result_count",
            "collections_searched",
            "duration_ms",
            "failed",
            "created_at",
        )
        read_only_fields = fields


class QueryLogFilterSerializer(serializers.Serializer):
    """Reads the query string of the log listing."""

    agent = OptionalUUIDField(required=False, allow_null=True)
