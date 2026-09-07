import uuid

from django.db import migrations

DEFAULT_COLLECTION_NAME = "local-minilm-l6-v2"
ROOT_FOLDER_NAME = "root"


def create_defaults(apps, schema_editor):
    """Create the default collection and the root folder of the tree.

    Both are required for the instance to work: files dropped at the top level
    live in the root folder, and folders created without an explicit model use
    the free local embedding model.
    """
    Collection = apps.get_model("drive", "Collection")
    Folder = apps.get_model("drive", "Folder")
    collection = Collection.objects.create(
        collection_id=uuid.uuid4(),
        name=DEFAULT_COLLECTION_NAME,
        provider="local",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        vector_size=384,
        is_default=True,
    )
    Folder.objects.create(
        folder_id=uuid.uuid4(),
        parent=None,
        name=ROOT_FOLDER_NAME,
        collection=collection,
    )


def remove_defaults(apps, schema_editor):
    """Remove the root folder and the default collection."""
    Collection = apps.get_model("drive", "Collection")
    Folder = apps.get_model("drive", "Folder")
    Folder.objects.filter(parent__isnull=True, name=ROOT_FOLDER_NAME).delete()
    Collection.objects.filter(name=DEFAULT_COLLECTION_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("drive", "0001_initial")]

    operations = [migrations.RunPython(create_defaults, remove_defaults)]
