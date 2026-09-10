"""Serializers for collections, folders and documents."""

from django.conf import settings
from rest_framework import serializers

from apps.common.fields import OptionalUUIDField
from apps.drive.models import Collection, Document, EmbeddingProvider, Folder
from apps.drive.services import is_within
from apps.ingestion.models import ProcessingJob

MIN_CHUNK_WORDS = 20


class ChunkingValidationMixin:
    """Checks the chunk size a collection is asked to split its text with."""

    def validate_chunking(self, attrs, instance=None):
        """Reject a chunk size that would make the stored text unusable.

        Takes the submitted values and the collection being changed, if there
        is one. A chunk shorter than a couple of sentences carries no context
        for the model to embed, and an overlap as long as the chunk repeats
        every chunk whole and doubles what is stored for no gain. Returns the
        values unchanged.
        """
        words = attrs.get("chunk_words", getattr(instance, "chunk_words", None))
        overlap = attrs.get("chunk_overlap_words", getattr(instance, "chunk_overlap_words", None))
        if words is not None and words < MIN_CHUNK_WORDS:
            raise serializers.ValidationError(
                {"chunk_words": f"A chunk needs at least {MIN_CHUNK_WORDS} words to mean anything"}
            )
        effective_words = words if words is not None else settings.CHUNK_WORDS
        if overlap is not None and overlap >= effective_words:
            raise serializers.ValidationError(
                {"chunk_overlap_words": "The overlap has to be smaller than the chunk"}
            )
        return attrs


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
            "chunk_words",
            "chunk_overlap_words",
            "created_at",
        )
        read_only_fields = ("collection_id", "created_at")


class CollectionCreateSerializer(ChunkingValidationMixin, CollectionSerializer):
    """Registers a collection, refusing the clashes with a reason to act on.

    The validators the framework builds from the table's own constraints are
    dropped, because they answer a clash by listing the columns involved. The
    checks below cover exactly the same ground and instead name the collection
    already holding the model, which is the collection the owner wants to use.
    The constraints stay on the table, so nothing gets past them either way.
    """

    class Meta(CollectionSerializer.Meta):
        validators = []

    def validate_name(self, value):
        """Reject a name already used by another collection.

        The name reaches Qdrant verbatim and never changes afterwards, so a
        clash has to be caught before the collection exists.
        """
        if Collection.objects.filter(name=value).exists():
            raise serializers.ValidationError("A collection with this name already exists")
        return value

    def validate(self, attrs):
        """Check the endpoint matches the provider, and the model is free.

        A local collection must carry no base URL and one served by an API
        must carry one, so that the provider always tells the whole story of
        where the vectors come from.

        Two collections on the same model would hold two copies of the same
        vectors, and a folder pointed at either would search only half of what
        was indexed. The name of the collection already holding the model is
        given, because the useful next step is to point the folder at that one.
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
        existing = Collection.objects.filter(
            provider=provider, base_url=base_url, model_name=attrs.get("model_name")
        ).first()
        if existing:
            raise serializers.ValidationError(
                {"model_name": f"The collection {existing.name} already uses this model"}
            )
        return self.validate_chunking(attrs)


class CollectionUpdateSerializer(ChunkingValidationMixin, serializers.ModelSerializer):
    """Changes the few things about a collection that are safe to change."""

    class Meta:
        model = Collection
        fields = ("is_default", "chunk_words", "chunk_overlap_words")

    def validate(self, attrs):
        """Check the chunk size against what the collection already holds."""
        return self.validate_chunking(attrs, self.instance)


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
        """Reject a clashing name, and a model chosen below the first level.

        Only a folder created directly under the root may choose its embedding
        model. Deeper folders inherit their parent's, so that one branch of the
        tree is searched with one model throughout and a subtree cannot end up
        split across two collections that cannot be compared.
        """
        if Folder.objects.filter(parent=attrs["parent"], name=attrs["name"]).exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists here"}
            )
        if "collection" in attrs and attrs["parent"].parent_id is not None:
            raise serializers.ValidationError(
                {"collection": "Only a folder directly under the root may choose its model"}
            )
        return attrs


class FolderUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    parent = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all(), required=False)
    collection = serializers.PrimaryKeyRelatedField(
        queryset=Collection.objects.all(), required=False
    )

    def validate(self, attrs):
        """Reject renames that clash and moves that would build a cycle.

        The root folder cannot be moved, and no folder may be placed inside
        its own subtree, which would detach that subtree from the tree.

        Only the root may have its model changed, since the root is where the
        instance says which model it uses by default. Any other folder keeps
        the model its documents were vectorised with.
        """
        folder = self.instance
        if "collection" in attrs and folder.parent_id is not None:
            raise serializers.ValidationError(
                {"collection": "Only the root folder may have its model changed"}
            )
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


class DocumentDetailSerializer(DocumentSerializer):
    last_error = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ("last_error",)
        read_only_fields = fields

    def get_last_error(self, document):
        """Return why the most recent processing run failed, if it did.

        A failed status on its own tells the owner that something broke but
        not what, which leaves nothing to act on. The reason is read here
        rather than in the listing because it costs one query per document,
        and a folder of a hundred files should not pay for it.
        """
        job = ProcessingJob.objects.filter(document=document).first()
        return job.error_message if job else None


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


class DocumentFilterSerializer(serializers.Serializer):
    """Reads the query string of the document listing.

    The identifier is checked here rather than in the view, so a malformed one
    is answered as the bad request it is instead of reaching the query layer
    and surfacing as a 500.
    """

    folder = OptionalUUIDField(required=False, allow_null=True)


class DocumentUploadSerializer(serializers.Serializer):
    """Reads an upload: the file, where it goes and what it is called."""

    file = serializers.FileField()
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all())
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        """Reject a name already taken inside the destination folder.

        The table refuses the clash too, but a constraint reaching the caller
        as a failed request says only that something went wrong; the folder
        and the name are what the owner needs in order to choose another.
        """
        name = attrs.get("name") or attrs["file"].name
        if Document.objects.filter(folder=attrs["folder"], name=name).exists():
            raise serializers.ValidationError(
                {"name": "A document with this name already exists in that folder"}
            )
        return attrs
