"""Serializers for collections, folders and documents."""

from django.conf import settings
from rest_framework import serializers

from apps.common import secrets
from apps.common.fields import OptionalUUIDField
from apps.drive.models import Collection, Document, EmbeddingProvider, Folder
from apps.drive.services import is_within
from apps.ingestion.extraction import can_extract
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
        bar = attrs.get("minimum_score", getattr(instance, "minimum_score", None))
        if bar is not None and not -1 <= bar <= 1:
            raise serializers.ValidationError(
                {"minimum_score": "A cosine similarity runs from -1 to 1"}
            )
        return attrs


class ApiKeyMixin:
    """Takes a credential in and never lets one back out.

    The key is write only and the reply says only whether one is held. A panel
    that could read a stored credential back would put it in a browser, in a
    cache and in whatever logs the answer passes through, which is a strange
    thing to do to a secret that was deliberately encrypted in its row.
    """

    def store_api_key(self, validated_data):
        """Move a submitted credential into its encrypted form.

        Takes the validated data and returns it with the credential replaced by
        the encrypted text. An empty value clears whatever was stored, which is
        how a collection is moved back to a key kept in the environment.
        """
        if "api_key" not in validated_data:
            return validated_data
        key = validated_data.pop("api_key")
        try:
            validated_data["encrypted_api_key"] = secrets.encrypt(key) if key else ""
        except secrets.EncryptionUnavailable as error:
            raise serializers.ValidationError({"api_key": [str(error)]}) from error
        return validated_data

    def create(self, validated_data):
        """Register the collection with its credential encrypted."""
        return super().create(self.store_api_key(validated_data))

    def update(self, instance, validated_data):
        """Change the collection, replacing the credential when one is given."""
        return super().update(instance, self.store_api_key(validated_data))


class CollectionSerializer(serializers.ModelSerializer):
    has_api_key = serializers.SerializerMethodField()

    def get_has_api_key(self, collection):
        """Report whether a credential is stored, without ever showing it."""
        return bool(collection.encrypted_api_key)

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
            "max_tokens",
            "minimum_score",
            "query_prefix",
            "passage_prefix",
            "has_api_key",
            "created_at",
        )
        read_only_fields = ("collection_id", "created_at")


class CollectionCreateSerializer(ApiKeyMixin, ChunkingValidationMixin, CollectionSerializer):
    """Registers a collection, refusing the clashes with a reason to act on.

    The validators the framework builds from the table's own constraints are
    dropped, because they answer a clash by listing the columns involved. The
    checks below cover exactly the same ground and instead name the collection
    already holding the model, which is the collection the owner wants to use.
    The constraints stay on the table, so nothing gets past them either way.
    """

    api_key = serializers.CharField(
        max_length=500, required=False, allow_blank=True, write_only=True
    )

    class Meta(CollectionSerializer.Meta):
        validators = []
        fields = CollectionSerializer.Meta.fields + ("api_key",)

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


class CollectionUpdateSerializer(
    ApiKeyMixin, ChunkingValidationMixin, serializers.ModelSerializer
):
    """Changes the few things about a collection that are safe to change."""

    api_key = serializers.CharField(
        max_length=500, required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = Collection
        fields = (
            "is_default",
            "chunk_words",
            "chunk_overlap_words",
            "max_tokens",
            "minimum_score",
            "query_prefix",
            "passage_prefix",
            "api_key",
        )

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
    is_indexable = serializers.SerializerMethodField()

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
            "is_indexable",
            "chunk_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_is_indexable(self, document):
        """Report whether this build can read the file at all.

        The panel offers the switch only when it can, so that a file nobody
        can read is never queued to fail an hour later.
        """
        return can_extract(document.content_type)


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
        """Reject a clashing name, and a switch on a file nobody can read.

        Queueing a file this build cannot read fails an hour later with the
        owner none the wiser; refusing here says so while they are looking.
        """
        document = self.instance
        folder = attrs.get("folder", document.folder)
        name = attrs.get("name", document.name)
        clash = Document.objects.filter(folder=folder, name=name).exclude(pk=document.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name": "A document with this name already exists in that folder"}
            )
        if attrs.get("is_agent_active") and not can_extract(document.content_type):
            raise serializers.ValidationError(
                {
                    "is_agent_active": (
                        f"Files of type {document.content_type} cannot be read by this "
                        "build, so there is nothing to index"
                    )
                }
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
