"""Tests for the pieces that turn permissions and hits into an answer."""

from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.access.models import Permission, PermissionEffect
from apps.agents.models import Agent
from apps.agents.tokens import issue_token
from apps.drive.models import Collection, Document, Folder
from apps.ingestion.embeddings import EmbeddingError
from apps.ingestion import vectors
from apps.search.service import confirm_against_database, fuse, narrow_to_folder
from apps.search.views import SearchThrottle


def make_result(document_id, chunk_index, score, collection="one"):
    """Build the shape a Qdrant hit takes once the search has read it."""
    return {
        "document_id": str(document_id),
        "folder_id": "f",
        "chunk_index": chunk_index,
        "text": "t",
        "score": score,
        "collection": collection,
    }


class AccessFilterTests(TestCase):
    """The filter that decides which stored chunks an agent is shown."""

    def test_a_scope_allowing_nothing_refuses_to_become_a_filter(self):
        """Two empty lists would match every active chunk, so they must not build one."""
        with self.assertRaises(ValueError):
            vectors.access_filter([], [], [])

    def test_every_filter_demands_the_chunk_be_active_for_agents(self):
        """A document whose switch is off is out of reach whatever the permissions say."""
        built = vectors.access_filter(["folder"], [], [])
        self.assertEqual(built.must[0].key, "is_agent_active")
        self.assertTrue(built.must[0].match.value)

    def test_allowed_folders_and_documents_become_alternatives(self):
        """Belonging to a permitted folder or to a permitted document both qualify."""
        built = vectors.access_filter(["folder"], ["document"], [])
        self.assertEqual(len(built.must[1].should), 2)

    def test_a_denied_document_becomes_an_exclusion(self):
        """A deny has to remove chunks the folder clause is still matching."""
        built = vectors.access_filter(["folder"], [], ["document"])
        self.assertEqual(built.must_not[0].key, "document_id")


class FusionTests(TestCase):
    """How results coming from different embedding models are merged."""

    def test_a_single_collection_keeps_the_order_it_came_in(self):
        """With one model the similarities are comparable, so nothing is rearranged."""
        results = [make_result("a", 0, 0.9), make_result("b", 0, 0.4)]
        self.assertEqual([r["document_id"] for r in fuse([results], 10)], ["a", "b"])

    def test_two_collections_are_merged_by_position_and_not_by_score(self):
        """A similarity from one model says nothing about one from another model."""
        first = [make_result("a", 0, 0.60, "one"), make_result("b", 0, 0.50, "one")]
        second = [make_result("c", 0, 0.38, "two")]
        merged = [result["document_id"] for result in fuse([first, second], 10)]
        self.assertEqual(merged[0], "a")
        self.assertLess(merged.index("c"), merged.index("b"))

    def test_the_limit_caps_what_comes_back_after_merging(self):
        """The cost of an answer is set by this limit, not by how many were consulted."""
        first = [make_result("a", 0, 0.9), make_result("b", 0, 0.8)]
        second = [make_result("c", 0, 0.7), make_result("d", 0, 0.6)]
        self.assertEqual(len(fuse([first, second], 2)), 2)

    def test_the_same_chunk_found_twice_is_returned_once(self):
        """A chunk reachable through two collections must not take two of the slots."""
        first = [make_result("a", 0, 0.9, "one")]
        second = [make_result("a", 0, 0.5, "two")]
        self.assertEqual(len(fuse([first, second], 10)), 1)


class NarrowingTests(TestCase):
    """Restricting a scope to one folder and everything under it."""

    def setUp(self):
        """Build two sibling branches and a scope that reaches both."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.wanted = Folder.objects.create(
            name="Wanted", parent=self.root, collection=self.collection
        )
        self.nested = Folder.objects.create(
            name="Nested", parent=self.wanted, collection=self.collection
        )
        self.other = Folder.objects.create(
            name="Other", parent=self.root, collection=self.collection
        )
        self.access = {
            self.collection.pk: {
                "folders": [self.wanted.pk, self.nested.pk, self.other.pk],
                "documents": [],
                "denied_documents": [],
            }
        }

    def test_narrowing_keeps_the_folder_and_what_hangs_below_it(self):
        """Scoping a search to a folder includes its whole subtree, not just itself."""
        narrowed = narrow_to_folder(self.access, self.wanted)
        self.assertEqual(
            sorted(narrowed[self.collection.pk]["folders"], key=str),
            sorted([self.wanted.pk, self.nested.pk], key=str),
        )

    def test_narrowing_drops_the_branches_outside_the_folder(self):
        """A sibling branch is not part of the subtree and must not be searched."""
        narrowed = narrow_to_folder(self.access, self.wanted)
        self.assertNotIn(self.other.pk, narrowed[self.collection.pk]["folders"])

    def test_narrowing_to_a_folder_that_does_not_exist_yields_nothing(self):
        """An agent must not learn from the answer whether a folder was ever created."""
        self.assertEqual(narrow_to_folder(self.access, None), {})


class DatabaseConfirmationTests(TestCase):
    """Checking each result against the database before it is handed over."""

    def setUp(self):
        """Register a document in a reachable folder, active and indexed."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.reachable = Folder.objects.create(
            name="Reachable", parent=self.root, collection=self.collection
        )
        self.elsewhere = Folder.objects.create(
            name="Elsewhere", parent=self.root, collection=self.collection
        )
        self.document = Document.objects.create(
            folder=self.reachable,
            name="report.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="report.txt",
            is_agent_active=True,
        )
        self.access = {
            self.collection.pk: {
                "folders": [self.reachable.pk],
                "documents": [],
                "denied_documents": [],
            }
        }

    def confirm(self):
        """Run one result for the test document through the confirmation."""
        return confirm_against_database(
            [make_result(self.document.pk, 0, 0.5)], self.access
        )

    def test_a_result_carries_the_name_its_document_has_now(self):
        """Names are read from the database, so renaming never reindexes anything."""
        self.document.name = "renamed.txt"
        self.document.save(update_fields=["name"])
        self.assertEqual(self.confirm()[0]["document_name"], "renamed.txt")

    def test_a_result_whose_document_was_deleted_is_dropped(self):
        """Chunks that outlive their document stop answering, however they survived."""
        result = make_result(self.document.pk, 0, 0.5)
        self.document.delete()
        self.assertEqual(confirm_against_database([result], self.access), [])

    def test_a_result_whose_document_was_switched_off_is_dropped(self):
        """Withdrawing access must hold even if the stored payload never heard of it."""
        self.document.is_agent_active = False
        self.document.save(update_fields=["is_agent_active"])
        self.assertEqual(self.confirm(), [])

    def test_a_result_whose_document_moved_out_of_reach_is_dropped(self):
        """A document moved into a folder the agent cannot read stops being returned."""
        self.document.folder = self.elsewhere
        self.document.save(update_fields=["folder"])
        self.assertEqual(self.confirm(), [])

    def test_a_result_denied_in_its_own_right_is_dropped(self):
        """A deny on the document is checked again here, not trusted to the filter."""
        self.access[self.collection.pk]["denied_documents"] = [self.document.pk]
        self.assertEqual(self.confirm(), [])

    def test_a_result_reports_the_folder_the_document_sits_in_now(self):
        """The location comes from the database, not from what was indexed."""
        self.assertEqual(self.confirm()[0]["folder_id"], str(self.reachable.pk))


TEST_RATES = {"search": "3/min"}


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class SearchEndpointTests(TestCase):
    """What the endpoint answers, as an agent actually sees it over HTTP."""

    def setUp(self):
        """Issue a token for an agent that has been granted nothing yet."""
        cache.clear()
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.agent = Agent.objects.create(name="caller")
        self.token = issue_token(self.agent)[1]

    def search(self, payload):
        """Post a search as the agent under test, over a secure connection.

        Production settings redirect plain requests, so the test client has to
        speak the same way a caller behind the proxy does.
        """
        return self.client.post(
            "/api/search/",
            payload,
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_a_request_without_a_token_is_refused(self):
        """The endpoint is for agents, so an anonymous caller never reaches it."""
        response = self.client.post(
            "/api/search/", {"query": "anything"}, content_type="application/json", secure=True
        )
        self.assertEqual(response.status_code, 401)

    def test_a_folder_out_of_reach_and_one_that_does_not_exist_answer_alike(self):
        """The answer must not tell an agent which folders were ever created."""
        unreadable = self.search({"query": "q", "folder": str(self.root.pk)})
        missing = self.search({"query": "q", "folder": "00000000-0000-4000-8000-000000000000"})
        self.assertEqual(unreadable.status_code, missing.status_code)
        self.assertEqual(unreadable.json(), missing.json())
        self.assertEqual(unreadable.json(), {"results": []})

    def test_an_unreachable_embedding_model_answers_service_unavailable(self):
        """An automated caller has to tell a broken dependency from a bad request."""
        Permission.objects.create(
            agent=self.agent, folder=self.root, effect=PermissionEffect.ALLOW
        )
        with patch(
            "apps.search.service.embed_texts", side_effect=EmbeddingError("endpoint down")
        ):
            response = self.search({"query": "q"})
        self.assertEqual(response.status_code, 503)

    def test_an_agent_that_searches_too_often_is_throttled(self):
        """Every call costs an embedding, so a leaked token cannot run up a bill.

        The rate is replaced on the throttle class rather than in the settings,
        because the framework reads the configured rates once when the class is
        first imported and never looks at them again.
        """
        with patch.object(SearchThrottle, "THROTTLE_RATES", TEST_RATES):
            codes = [self.search({"query": "q"}).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_the_allowance_is_counted_for_each_agent_on_its_own(self):
        """One noisy agent must not spend the allowance of every other agent."""
        other = Agent.objects.create(name="quiet")
        with patch.object(SearchThrottle, "THROTTLE_RATES", TEST_RATES):
            for _ in range(4):
                self.search({"query": "q"})
            response = self.client.post(
                "/api/search/",
                {"query": "q"},
                content_type="application/json",
                secure=True,
                HTTP_AUTHORIZATION=f"Bearer {issue_token(other)[1]}",
            )
        self.assertEqual(response.status_code, 200)
