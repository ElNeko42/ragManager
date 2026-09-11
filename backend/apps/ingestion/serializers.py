"""Serializers for trying an embedding endpoint from the panel."""

from rest_framework import serializers

from apps.common.fields import OptionalUUIDField


class EndpointSerializer(serializers.Serializer):
    """What every call against an endpoint has to name."""

    base_url = serializers.URLField(max_length=500)
    api_key = serializers.CharField(
        max_length=500, required=False, allow_blank=True, write_only=True
    )
    collection = OptionalUUIDField(required=False, allow_null=True)


class ModelListSerializer(EndpointSerializer):
    """Asks an endpoint which models it serves.

    The provider is named so that its own way of naming embedding models can be
    used to tell them from the chat models beside them. Asking for all of them
    is how somebody reaches a model whose name gives nothing away.
    """

    provider = serializers.CharField(max_length=64, required=False, allow_blank=True)
    include_all = serializers.BooleanField(required=False, default=False)


class ProbeSerializer(EndpointSerializer):
    """Asks one model of an endpoint what it answers with."""

    model_name = serializers.CharField(max_length=200)
