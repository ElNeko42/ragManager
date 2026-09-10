"""Stop two collections from claiming the same embedding model."""

from django.db import migrations, models


def refuse_existing_duplicates(apps, schema_editor):
    """Stop the migration with an explanation instead of a constraint error.

    An instance registered before this rule existed may hold two collections
    pointing at the same model, and the database would refuse the constraint
    with a message naming neither of them. This looks first and says which
    collections clash, because deciding which one to keep is the operator's
    call: their documents were vectorised separately and merging them is not
    something a migration can do.
    """
    Collection = apps.get_model("drive", "Collection")
    seen = {}
    clashes = []
    for collection in Collection.objects.all().order_by("created_at"):
        key = (collection.provider, collection.base_url, collection.model_name)
        if key in seen:
            clashes.append(f"{collection.name} and {seen[key]} both use {collection.model_name}")
        else:
            seen[key] = collection.name
    if clashes:
        raise RuntimeError(
            "Two collections cannot share an embedding model: "
            + "; ".join(clashes)
            + ". Move the folders off one of them and delete it, then migrate again."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("drive", "0005_folder_folders_only_one_root"),
    ]

    operations = [
        migrations.RunPython(refuse_existing_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.UniqueConstraint(
                fields=("provider", "base_url", "model_name"), name="collections_unique_model"
            ),
        ),
    ]
