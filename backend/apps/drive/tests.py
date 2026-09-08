"""Tests for keeping the vector store in step with the documents table."""

from unittest.mock import patch

from django.test import TestCase

from apps.drive.models import Collection, Document, Folder, ProcessingStatus
from apps.drive.services import update_document


class VectorStoreSynchronisationTests(TestCase):
    """What an update to a document pushes to where its chunks are stored."""

    def setUp(self):
        """Register an indexed document that agents can currently read."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.elsewhere = Folder.objects.create(
            name="Elsewhere", parent=self.root, collection=self.collection
        )
        self.document = Document.objects.create(
            folder=self.root,
            name="report.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="report.txt",
            is_agent_active=True,
            processing_status=ProcessingStatus.READY,
            chunk_count=1,
        )

    def update(self, changes):
        """Apply changes to the document and capture what reached the store."""
        with patch("apps.drive.services.ingestion") as ingestion:
            self.document = update_document(self.document, changes)
        return ingestion

    def test_switching_the_flag_off_pushes_the_new_state(self):
        """Withdrawing access has to reach the store, not only the table."""
        ingestion = self.update({"is_agent_active": False})
        pushed = ingestion.apply_payload.call_args.args[2]
        self.assertFalse(pushed["is_agent_active"])

    def test_a_move_pushes_the_folder_the_document_now_sits_in(self):
        """Permissions are matched against the folder recorded beside the chunk."""
        ingestion = self.update({"folder": self.elsewhere})
        pushed = ingestion.apply_payload.call_args.args[2]
        self.assertEqual(pushed["folder_id"], str(self.elsewhere.pk))

    def test_the_whole_state_is_pushed_rather_than_only_what_changed(self):
        """Pushing the difference cannot be repeated once the row already holds it."""
        ingestion = self.update({"name": "renamed.txt"})
        pushed = ingestion.apply_payload.call_args.args[2]
        self.assertEqual(set(pushed), {"folder_id", "is_agent_active"})

    def test_applying_the_same_change_twice_pushes_it_twice(self):
        """A push lost to an unreachable store must be repeatable by trying again."""
        self.update({"is_agent_active": False})
        ingestion = self.update({"is_agent_active": False})
        self.assertFalse(ingestion.apply_payload.call_args.args[2]["is_agent_active"])

    def test_turning_the_flag_on_for_a_document_never_indexed_queues_it(self):
        """There is nothing to update in the store until the chunks exist."""
        self.document.is_agent_active = False
        self.document.processing_status = None
        self.document.save(update_fields=["is_agent_active", "processing_status"])
        ingestion = self.update({"is_agent_active": True})
        ingestion.enqueue.assert_called_once()
        ingestion.apply_payload.assert_not_called()
