"""Tests for keeping the vector store in step with the documents table."""

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.drive.models import (
    Collection,
    Document,
    EmbeddingProvider,
    Folder,
    ProcessingStatus,
)
from apps.drive.serializers import DocumentDetailSerializer
from apps.drive.services import update_document
from apps.ingestion.models import ProcessingJob
from apps.ingestion.tasks import redact


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

    def test_a_move_into_another_collection_discards_what_was_indexed(self):
        """Vectors of one embedding model mean nothing to another one."""
        other = Collection.objects.create(
            name="other-model",
            provider=self.collection.provider,
            base_url=self.collection.base_url,
            model_name="another-model",
            vector_size=self.collection.vector_size,
        )
        far = Folder.objects.create(name="Far", parent=self.root, collection=other)
        ingestion = self.update({"folder": far})
        ingestion.discard_vectors.assert_called_once_with(self.collection.name, self.document.pk)

    def test_a_move_into_another_collection_queues_the_document_again(self):
        """A document left unindexed after a move would silently stop answering."""
        other = Collection.objects.create(
            name="second-model",
            provider=self.collection.provider,
            base_url=self.collection.base_url,
            model_name="another-model",
            vector_size=self.collection.vector_size,
        )
        far = Folder.objects.create(name="Far", parent=self.root, collection=other)
        ingestion = self.update({"folder": far})
        ingestion.enqueue.assert_called_once()
        self.document.refresh_from_db()
        self.assertIsNone(self.document.processing_status)
        self.assertEqual(self.document.chunk_count, 0)

    def test_turning_the_flag_on_for_a_document_never_indexed_queues_it(self):
        """There is nothing to update in the store until the chunks exist."""
        self.document.is_agent_active = False
        self.document.processing_status = None
        self.document.save(update_fields=["is_agent_active", "processing_status"])
        ingestion = self.update({"is_agent_active": True})
        ingestion.enqueue.assert_called_once()
        ingestion.apply_payload.assert_not_called()


class LastErrorTests(TestCase):
    """What the detail view tells the owner about a run that failed."""

    def setUp(self):
        """Register a document that has been through the queue."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.document = Document.objects.create(
            folder=self.root,
            name="report.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="report.txt",
            processing_status=ProcessingStatus.FAILED,
        )

    def serialize(self):
        """Return the detail payload the API would send for the document."""
        return DocumentDetailSerializer(self.document).data

    def test_a_document_that_never_ran_reports_no_error(self):
        """A field that invents a failure would send the owner chasing nothing."""
        self.assertIsNone(self.serialize()["last_error"])

    def test_the_reason_of_the_failed_run_is_reported(self):
        """A failed status with no reason leaves the owner nothing to act on."""
        ProcessingJob.objects.create(
            document=self.document,
            status=ProcessingStatus.FAILED,
            error_message="ValueError: no text could be extracted",
        )
        self.assertEqual(
            self.serialize()["last_error"], "ValueError: no text could be extracted"
        )

    def test_the_most_recent_run_is_the_one_reported(self):
        """A stale reason from an older attempt describes a problem already gone."""
        ProcessingJob.objects.create(
            document=self.document,
            status=ProcessingStatus.FAILED,
            error_message="older",
        )
        ProcessingJob.objects.create(
            document=self.document,
            status=ProcessingStatus.FAILED,
            error_message="newer",
        )
        self.assertEqual(self.serialize()["last_error"], "newer")

    def test_a_run_that_succeeded_carries_no_reason(self):
        """An empty message must not read as an unexplained failure."""
        ProcessingJob.objects.create(document=self.document, status=ProcessingStatus.READY)
        self.assertFalse(self.serialize()["last_error"])


class ErrorRedactionTests(TestCase):
    """What of a raised exception is allowed to reach the database."""

    def test_credentials_carried_in_a_url_are_removed(self):
        """A password stored in plain text is a password waiting to be read."""
        message = "ConnectionError: cannot reach https://rag:s3cr3t@vectors.example/v1"
        self.assertEqual(
            redact(message),
            "ConnectionError: cannot reach https://***@vectors.example/v1",
        )

    def test_a_url_without_credentials_is_left_alone(self):
        """Blanking a plain endpoint would hide the one clue the owner needs."""
        message = "ConnectionError: cannot reach https://vectors.example/v1"
        self.assertEqual(redact(message), message)

    def test_an_email_address_in_a_message_is_left_alone(self):
        """An at sign is not by itself a secret, and the text has to stay readable."""
        message = "ValueError: owner@example.com is not a folder"
        self.assertEqual(redact(message), message)


class FolderRenameEndpointTests(TestCase):
    """What the owner can change about a folder over HTTP."""

    def setUp(self):
        """Sign in an owner and give them a folder under the root."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="a-long-enough-password"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        self.folder = Folder.objects.create(
            name="Invoices", parent=self.root, collection=self.root.collection
        )

    def patch(self, folder, changes):
        """Send a change to one folder as the signed-in owner."""
        return self.client.patch(
            f"/api/folders/{folder.pk}/",
            changes,
            content_type="application/json",
            secure=True,
        )

    def test_the_owner_can_rename_a_folder(self):
        """The panel offers renaming, so the endpoint behind it has to answer."""
        response = self.patch(self.folder, {"name": "Receipts"})
        self.assertEqual(response.status_code, 200)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.name, "Receipts")

    def test_the_new_name_comes_back_in_the_reply(self):
        """The panel puts the reply straight into its tree without asking again."""
        self.assertEqual(self.patch(self.folder, {"name": "Receipts"}).json()["name"], "Receipts")

    def test_an_empty_name_is_refused(self):
        """A folder with no name is unreachable in a tree drawn from names."""
        response = self.patch(self.folder, {"name": "   "})
        self.assertEqual(response.status_code, 400)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.name, "Invoices")

    def test_a_signed_out_visitor_cannot_rename(self):
        """Renaming is the owner's, and an agent token has no business here."""
        self.client.logout()
        self.assertEqual(self.patch(self.folder, {"name": "Receipts"}).status_code, 401)


@patch("apps.drive.services.schedule_object_cleanup")
@patch("apps.drive.services.ingestion")
class FolderDeletionEndpointTests(TestCase):
    """What deleting a folder takes with it, and what it must refuse."""

    def setUp(self):
        """Sign in an owner and build a branch three folders deep."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="a-long-enough-password"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        self.branch = Folder.objects.create(
            name="Branch", parent=self.root, collection=self.root.collection
        )
        self.twig = Folder.objects.create(
            name="Twig", parent=self.branch, collection=self.root.collection
        )
        self.leaf = Document.objects.create(
            folder=self.twig,
            name="deep.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="deep.txt",
            processing_status=ProcessingStatus.READY,
            chunk_count=2,
        )

    def delete(self, folder):
        """Ask for one folder to be deleted as the signed-in owner."""
        return self.client.delete(f"/api/folders/{folder.pk}/", secure=True)

    def test_the_root_folder_cannot_be_deleted(self, ingestion, cleanup):
        """The root anchors the tree and every permission lookup above it."""
        response = self.delete(self.root)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Folder.objects.filter(pk=self.root.pk).exists())

    def test_deleting_a_branch_takes_the_folders_below_it(self, ingestion, cleanup):
        """A folder left behind with no parent is unreachable in the panel."""
        self.assertEqual(self.delete(self.branch).status_code, 204)
        self.assertFalse(Folder.objects.filter(pk=self.twig.pk).exists())

    def test_deleting_a_branch_takes_the_documents_below_it(self, ingestion, cleanup):
        """A document whose folder is gone can never be reached or removed again."""
        self.delete(self.branch)
        self.assertFalse(Document.objects.filter(pk=self.leaf.pk).exists())

    def test_the_stored_files_of_the_branch_are_queued_for_removal(self, ingestion, cleanup):
        """Rows going without their objects leaves the bucket growing forever."""
        self.delete(self.branch)
        self.assertEqual(cleanup.call_args.args[0], ["deep.txt"])

    def test_the_vectors_of_the_branch_are_discarded(self, ingestion, cleanup):
        """Chunks left behind would answer searches about a deleted document."""
        self.delete(self.branch)
        ingestion.discard_vectors.assert_called_once_with(
            self.root.collection.name, self.leaf.pk
        )

    def test_the_parent_of_the_deleted_branch_survives(self, ingestion, cleanup):
        """Deletion runs downwards only, or one folder would empty the panel."""
        self.delete(self.branch)
        self.assertTrue(Folder.objects.filter(pk=self.root.pk).exists())

    def test_a_signed_out_visitor_cannot_delete(self, ingestion, cleanup):
        """Recursive deletion is the owner's, and no agent token reaches it."""
        self.client.logout()
        self.assertEqual(self.delete(self.branch).status_code, 401)
        self.assertTrue(Folder.objects.filter(pk=self.branch.pk).exists())


class CollectionRegistrationTests(TestCase):
    """What may be registered as an embedding model, and what may not."""

    def setUp(self):
        """Sign in an owner alongside the collection the instance ships with."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="a-long-enough-password"
        )
        self.client.force_login(self.owner)
        self.existing = Collection.objects.get(is_default=True)

    def register(self, **changes):
        """Register a collection, taking the sensible defaults from one model."""
        payload = {
            "name": "openai-large",
            "provider": "api",
            "base_url": "https://api.example.com/v1",
            "model_name": "text-embedding-3-large",
            "vector_size": 3072,
        }
        payload.update(changes)
        return self.client.post(
            "/api/collections/", payload, content_type="application/json", secure=True
        )

    def test_a_collection_for_a_new_model_is_registered(self):
        """The panel offers this, so the endpoint behind it has to answer."""
        self.assertEqual(self.register().status_code, 201)

    def test_a_second_collection_on_the_same_model_is_refused(self):
        """Two copies of the same vectors means each folder searches half of them."""
        self.register()
        response = self.register(name="openai-large-again")
        self.assertEqual(response.status_code, 400)
        self.assertIn("model_name", response.json())

    def test_the_refusal_names_the_collection_that_holds_the_model(self):
        """Knowing which one already has it turns the error into the next step."""
        self.register()
        self.assertIn("openai-large", response_text(self.register(name="another")))

    def test_the_same_model_at_another_endpoint_is_allowed(self):
        """One model served by two providers is two different things to reach."""
        self.register()
        response = self.register(name="mirror", base_url="https://other.example.com/v1")
        self.assertEqual(response.status_code, 201)

    def test_a_local_collection_may_not_carry_an_endpoint(self):
        """The provider has to tell the whole story of where vectors come from."""
        response = self.register(provider="local", base_url="https://api.example.com/v1")
        self.assertEqual(response.status_code, 400)

    def test_a_collection_served_by_an_api_needs_an_endpoint(self):
        """Without it there is nowhere to send the text to be embedded."""
        response = self.register(provider="api", base_url="")
        self.assertEqual(response.status_code, 400)

    def test_a_name_already_taken_is_refused(self):
        """The name reaches Qdrant verbatim and cannot be changed afterwards."""
        self.assertEqual(self.register(name=self.existing.name).status_code, 400)

    def test_the_database_refuses_a_duplicate_model_too(self):
        """A rule only in the serializer is one the API can be talked around."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Collection.objects.create(
                name="sneaked-in",
                provider=self.existing.provider,
                base_url=self.existing.base_url,
                model_name=self.existing.model_name,
                vector_size=self.existing.vector_size,
            )


def response_text(response):
    """Return the body of a response as one searchable string."""
    return response.content.decode("utf-8")


class FolderCollectionTests(TestCase):
    """Which folders may choose an embedding model, and which inherit one."""

    def setUp(self):
        """Sign in an owner with a second model and a first level folder."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="a-long-enough-password"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        self.other = Collection.objects.create(
            name="second-model",
            provider=EmbeddingProvider.LOCAL,
            model_name="another/model",
            vector_size=768,
        )
        self.first_level = Folder.objects.create(
            name="Branch", parent=self.root, collection=self.other
        )

    def create(self, name, parent, collection=None):
        """Ask for a folder, naming a collection only when one is given."""
        payload = {"name": name, "parent": str(parent.pk)}
        if collection is not None:
            payload["collection"] = str(collection.pk)
        return self.client.post(
            "/api/folders/", payload, content_type="application/json", secure=True
        )

    def test_a_folder_under_the_root_may_choose_its_model(self):
        """The first level is where a branch decides which model it uses."""
        response = self.create("Chosen", self.root, self.other)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["collection"], str(self.other.pk))

    def test_a_folder_deeper_down_may_not_choose_its_model(self):
        """A subtree split across two models cannot be searched as one."""
        response = self.create("Deeper", self.first_level, self.collection_of_root())
        self.assertEqual(response.status_code, 400)
        self.assertIn("collection", response.json())

    def test_a_folder_deeper_down_inherits_from_its_parent(self):
        """Inheriting is what keeps a branch on one model throughout."""
        response = self.create("Deeper", self.first_level)
        self.assertEqual(response.json()["collection"], str(self.other.pk))

    def test_a_folder_under_the_root_inherits_when_none_is_chosen(self):
        """Not choosing has to mean the instance default, not no model at all."""
        response = self.create("Plain", self.root)
        self.assertEqual(response.json()["collection"], str(self.collection_of_root().pk))

    def collection_of_root(self):
        """Return the model the root folder currently uses."""
        self.root.refresh_from_db()
        return self.root.collection


class BaseModelTests(TestCase):
    """What happens when the instance changes the model its root uses."""

    def setUp(self):
        """Sign in an owner with a second model and a document in the root."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="a-long-enough-password"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        self.previous = self.root.collection
        self.other = Collection.objects.create(
            name="second-model",
            provider=EmbeddingProvider.LOCAL,
            model_name="another/model",
            vector_size=768,
        )
        self.document = Document.objects.create(
            folder=self.root,
            name="report.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="report.txt",
            is_agent_active=True,
            processing_status=ProcessingStatus.READY,
            chunk_count=3,
        )
        self.elsewhere = Folder.objects.create(
            name="Elsewhere", parent=self.root, collection=self.previous
        )

    def switch(self, folder, collection):
        """Point one folder at another model over HTTP."""
        return self.client.patch(
            f"/api/folders/{folder.pk}/",
            {"collection": str(collection.pk)},
            content_type="application/json",
            secure=True,
        )

    @patch("apps.drive.services.ingestion")
    def test_the_root_may_change_its_model(self, ingestion):
        """This is where the instance says which model it uses by default."""
        self.assertEqual(self.switch(self.root, self.other).status_code, 200)
        self.root.refresh_from_db()
        self.assertEqual(self.root.collection_id, self.other.pk)

    @patch("apps.drive.services.ingestion")
    def test_any_other_folder_may_not(self, ingestion):
        """Its documents were vectorised with the model it already has."""
        response = self.switch(self.elsewhere, self.other)
        self.assertEqual(response.status_code, 400)
        self.elsewhere.refresh_from_db()
        self.assertEqual(self.elsewhere.collection_id, self.previous.pk)

    @patch("apps.drive.services.ingestion")
    def test_documents_in_the_root_lose_the_vectors_of_the_old_model(self, ingestion):
        """Chunks of another model would answer searches they cannot be compared to."""
        self.switch(self.root, self.other)
        ingestion.discard_vectors.assert_called_once_with(self.previous.name, self.document.pk)

    @patch("apps.drive.services.ingestion")
    def test_documents_in_the_root_are_queued_again(self, ingestion):
        """A document left unindexed after the change silently stops answering."""
        self.switch(self.root, self.other)
        ingestion.enqueue.assert_called_once()
        self.document.refresh_from_db()
        self.assertIsNone(self.document.processing_status)
        self.assertEqual(self.document.chunk_count, 0)

    @patch("apps.drive.services.ingestion")
    def test_a_switched_off_document_is_not_queued(self, ingestion):
        """Its switch is the owner's intention and a model change is not consent."""
        self.document.is_agent_active = False
        self.document.save(update_fields=["is_agent_active"])
        self.switch(self.root, self.other)
        ingestion.enqueue.assert_not_called()

    @patch("apps.drive.services.ingestion")
    def test_folders_below_the_root_keep_their_own_model(self, ingestion):
        """A branch changing model under its documents is exactly what to avoid."""
        self.switch(self.root, self.other)
        self.elsewhere.refresh_from_db()
        self.assertEqual(self.elsewhere.collection_id, self.previous.pk)

    @patch("apps.drive.services.ingestion")
    def test_setting_the_model_it_already_has_changes_nothing(self, ingestion):
        """Re-saving the same choice must not throw away a working index."""
        self.switch(self.root, self.previous)
        ingestion.discard_vectors.assert_not_called()
        self.document.refresh_from_db()
        self.assertEqual(self.document.processing_status, ProcessingStatus.READY)


class PaginationTests(TestCase):
    """What a listing does once an instance holds more than a screenful."""

    def setUp(self):
        """Sign in as the owner with a folder holding several documents."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        for index in range(12):
            Document.objects.create(
                folder=self.root,
                name=f"file-{index:02d}.txt",
                content_type="text/plain",
                size_bytes=1,
                storage_key=f"documents/file-{index}",
            )

    def test_a_listing_says_how_many_there_are_in_total(self):
        """A page with no count leaves the panel unable to draw the next one."""
        response = self.client.get("/api/documents/", secure=True)
        self.assertEqual(response.json()["count"], 12)

    def test_a_listing_can_be_cut_into_pages(self):
        """Thousands of documents in one answer is what this is here to stop."""
        response = self.client.get("/api/documents/?page_size=5", secure=True)
        self.assertEqual(len(response.json()["results"]), 5)

    def test_a_page_points_at_the_one_after_it(self):
        """A caller with no link to the next page cannot walk the listing."""
        response = self.client.get("/api/documents/?page_size=5", secure=True)
        self.assertIsNotNone(response.json()["next"])

    def test_the_last_page_points_nowhere_further(self):
        """Walking the pages has to end, or the panel asks forever."""
        response = self.client.get("/api/documents/?page=3&page_size=5", secure=True)
        self.assertIsNone(response.json()["next"])

    def test_a_page_beyond_the_end_is_not_an_empty_success(self):
        """Answering a page that does not exist with nothing hides a bug."""
        response = self.client.get("/api/documents/?page=99", secure=True)
        self.assertEqual(response.status_code, 404)

    def test_a_caller_cannot_ask_for_the_whole_table_at_once(self):
        """A ceiling is what keeps the page size from undoing the paging."""
        response = self.client.get("/api/documents/?page_size=100000", secure=True)
        self.assertLessEqual(len(response.json()["results"]), settings.MAX_PAGE_SIZE)

    def test_the_folder_listing_is_paged_too(self):
        """The tree grows the same way the documents do."""
        response = self.client.get("/api/folders/", secure=True)
        self.assertIn("results", response.json())

    def test_a_malformed_folder_filter_is_a_bad_request(self):
        """A value that is not an identifier must not reach the query layer."""
        response = self.client.get("/api/documents/?folder=nonsense", secure=True)
        self.assertEqual(response.status_code, 400)

    def test_an_empty_folder_filter_means_no_filter(self):
        """A panel writes the parameter whether or not it holds anything."""
        response = self.client.get("/api/documents/?folder=", secure=True)
        self.assertEqual(response.json()["count"], 12)


class ReprocessEndpointTests(TestCase):
    """Putting a document that failed back in the queue."""

    def setUp(self):
        """Sign in as the owner with a document whose last run failed."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)
        self.root = Folder.objects.get(parent__isnull=True)
        self.document = Document.objects.create(
            folder=self.root,
            name="scan.pdf",
            content_type="application/pdf",
            size_bytes=10,
            storage_key="documents/scan.pdf",
            is_agent_active=True,
            processing_status=ProcessingStatus.FAILED,
        )

    def reprocess(self):
        """Ask for the document to be queued again."""
        return self.client.post(f"/api/documents/{self.document.pk}/reprocess/", secure=True)

    @patch("apps.drive.services.ingestion")
    def test_a_failed_document_can_be_queued_again(self, ingestion):
        """A run that failed for good is otherwise failed forever."""
        self.assertEqual(self.reprocess().status_code, 200)
        ingestion.enqueue.assert_called_once()

    @patch("apps.drive.services.ingestion")
    def test_a_document_no_agent_may_read_is_refused(self, ingestion):
        """Indexing what nothing is allowed to search spends the queue for nothing."""
        self.document.is_agent_active = False
        self.document.save(update_fields=["is_agent_active"])
        self.assertEqual(self.reprocess().status_code, 409)
        ingestion.enqueue.assert_not_called()

    def test_a_signed_out_visitor_cannot_queue_anything(self):
        """The queue is the owner's to spend, not a visitor's."""
        self.client.logout()
        self.assertEqual(self.reprocess().status_code, 401)


class CollectionChunkingEndpointTests(TestCase):
    """The chunk size an owner registers a collection with."""

    def setUp(self):
        """Sign in as the owner."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)

    def register(self, **extra):
        """Register a collection, with whatever chunk settings are given."""
        payload = {
            "name": "sized",
            "provider": "local",
            "model_name": "some/model",
            "vector_size": 384,
        }
        payload.update(extra)
        return self.client.post(
            "/api/collections/", payload, content_type="application/json", secure=True
        )

    def test_a_collection_may_name_the_size_its_text_is_split_into(self):
        """Every model reads a different amount, so the size belongs to it."""
        response = self.register(chunk_words=150, chunk_overlap_words=30)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["chunk_words"], 150)

    def test_a_collection_naming_no_size_leaves_it_to_the_instance(self):
        """One default is what keeps the form short for the common case."""
        self.assertIsNone(self.register().json()["chunk_words"])

    def test_an_overlap_as_long_as_the_chunk_is_refused(self):
        """Repeating every chunk whole doubles the store and gains nothing."""
        response = self.register(chunk_words=100, chunk_overlap_words=100)
        self.assertEqual(response.status_code, 400)

    def test_a_chunk_too_short_to_mean_anything_is_refused(self):
        """A chunk of three words carries no context for a model to embed."""
        self.assertEqual(self.register(chunk_words=3).status_code, 400)

    def test_the_size_can_be_changed_afterwards(self):
        """The size only decides how the next document is split."""
        collection = Collection.objects.get(pk=self.register().json()["collection_id"])
        response = self.client.patch(
            f"/api/collections/{collection.pk}/",
            {"chunk_words": 120},
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(response.json()["chunk_words"], 120)
