"""Serializers for collections, folders and documents."""

from rest_framework import serializers

from apps.drive.models import Collection, Document, EmbeddingProvider, Folder
from apps.drive.services import is_within


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = (
            "collection_id",
            "name",
            "provider",
            "base_url",
            "model_name",
            "vector_size",
            "is_default",
            "created_at",
        )
        read_only_fields = ("collection_id", "created_at")


class CollectionCreateSerializer(CollectionSerializer):
    def validate_name(self, value):
        """Reject a name already used by another collection.

        The name reaches Qdrant verbatim and never changes afterwards, so a
        clash has to be caught before the collection exists.
        """
        if Collection.objects.filter(name=value).exists():
            raise serializers.ValidationError("A collection with this name already exists")
        return value

    def validate(self, attrs):
        """Require a base URL for a collection served by an API.

        A local collection must not carry one, so that the provider always
        tells the whole story of where the vectors come from.
        """
        provider = attrs.get("provider")
        base_url = attrs.get("base_url", "")
        if provider == EmbeddingProvider.API and not base_url:
            raise serializers.ValidationError(
                {"base_url": "A collection served by an API needs the endpoint base URL"}
            )
        if provider == EmbeddingProvider.LOCAL and base_url:
            raise serializers.ValidationError(
                {"base_url": "A local collection does not use a base URL"}
            )
        return attrs


class CollectionUpdateSerializer(serializers.Serializer):
    is_default = serializers.BooleanField()


class FolderSerializer(serializers.ModelSerializer):
    is_root = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ("folder_id", "name", "parent", "collection", "is_root", "created_at", "updated_at")
        read_only_fields = ("folder_id", "created_at", "updated_at")

    def get_is_root(self, folder):
        """Report whether this folder is the top of the tree."""
        return folder.parent_id is None


class FolderCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    parent = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all())
    collection = serializers.PrimaryKeyRelatedField(
        queryset=Collection.objects.all(), required=False
    )

    def validate(self, attrs):
        """Reject a name already taken among the children of the parent."""
        if Folder.objects.filter(parent=attrs["parent"], name=attrs["name"]).exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists here"}
            )
        return attrs


class FolderUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    parent = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all(), required=False)

    def validate(self, attrs):
        """Reject renames that clash and moves that would build a cycle.

        The root folder cannot be moved, and no folder may be placed inside
        its own subtree, which would detach that subtree from the tree.
        """
        folder = self.instance
        parent = attrs.get("parent", folder.parent)
        name = attrs.get("name", folder.name)
        if folder.parent_id is None and "parent" in attrs:
            raise serializers.ValidationError({"parent": "The root folder cannot be moved"})
        if "parent" in attrs and is_within(folder, parent):
            raise serializers.ValidationError({"parent": "A folder cannot be moved inside itself"})
        clash = Folder.objects.filter(parent=parent, name=name).exclude(pk=folder.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists here"}
            )
        return attrs


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            "document_id",
            "folder",
            "name",
            "content_type",
            "size_bytes",
            "revision",
            "processing_status",
            "is_agent_active",
            "chunk_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DocumentUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all(), required=False)
    is_agent_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        """Reject a name already taken inside the destination folder."""
        document = self.instance
        folder = attrs.get("folder", document.folder)
        name = attrs.get("name", document.name)
        clash = Document.objects.filter(folder=folder, name=name).exclude(pk=document.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "A document with this name already exists in that folder"}
            )
        return attrs
