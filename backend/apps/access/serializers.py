"""Serializers for the access rules granted to agents."""

from rest_framework import serializers

from apps.access.models import Permission, PermissionEffect


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("permission_id", "agent", "folder", "document", "effect", "created_at")
        read_only_fields = ("permission_id", "created_at")

    def validate(self, attrs):
        """Reject rules with no target, two targets, or a duplicate target.

        A rule names either a folder or a document, never both and never
        neither, and an agent may hold only one rule over the same target so
        that the effective permission is never ambiguous.
        """
        folder = attrs.get("folder")
        document = attrs.get("document")
        if bool(folder) == bool(document):
            raise serializers.ValidationError(
                "A rule must name either a folder or a document, not both and not neither"
            )
        duplicate = Permission.objects.filter(
            agent=attrs["agent"], folder=folder, document=document
        )
        if duplicate.exists():
            raise serializers.ValidationError(
                "This agent already has a rule for that target; change it instead"
            )
        return attrs


class PermissionUpdateSerializer(serializers.Serializer):
    effect = serializers.ChoiceField(choices=PermissionEffect.choices)
