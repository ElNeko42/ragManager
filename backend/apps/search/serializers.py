"""Serializers for the search endpoint."""

from rest_framework import serializers

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
