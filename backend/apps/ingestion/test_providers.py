"""Tests for storing a credential and for trying an endpoint from the panel."""

import json
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.common import secrets
from apps.drive.models import Collection, EmbeddingProvider
from apps.ingestion import providers
from apps.ingestion.embeddings import EmbeddingError, get_api_key

KEY = "Zt8s-0dQ0aVQ9wYyq6a2Xb4wQ5dZ7cQm1nT8kP3rU9E="
OTHER_KEY = "9mQe1sVQ0aVQ9wYyq6a2Xb4wQ5dZ7cQm1nT8kP3rU9E="


@override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY)
class SecretStorageTests(TestCase):
    """What happens to a credential on its way into a row and back out."""

    def test_a_credential_survives_the_round_trip(self):
        """A stored key that cannot be read back is a key nobody can use."""
        self.assertEqual(secrets.decrypt(secrets.encrypt("sk-secret")), "sk-secret")

    def test_the_stored_text_is_not_the_credential(self):
        """The row is readable from the database, which is the whole point."""
        self.assertNotIn("sk-secret", secrets.encrypt("sk-secret"))

    def test_an_empty_credential_stores_nothing(self):
        """Clearing a key has to leave no key, not an encrypted empty string."""
        self.assertEqual(secrets.encrypt(""), "")

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=OTHER_KEY)
    def test_a_credential_written_with_another_key_reads_as_none(self):
        """A rotated key must fail as a missing credential, not as a crash."""
        with override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY):
            stored = secrets.encrypt("sk-secret")
        self.assertIsNone(secrets.decrypt(stored))

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=None)
    def test_storing_a_credential_with_nothing_to_encrypt_it_is_refused(self):
        """Falling back to plain text would be the worst possible answer."""
        with self.assertRaises(secrets.EncryptionUnavailable):
            secrets.encrypt("sk-secret")

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=None)
    def test_reading_a_credential_with_nothing_to_decrypt_it_reads_as_none(self):
        """An instance that lost its key still has to answer requests."""
        with override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY):
            stored = secrets.encrypt("sk-secret")
        self.assertIsNone(secrets.decrypt(stored))

    def test_a_key_that_is_not_a_key_says_so(self):
        """A truncated variable is a typo to correct, not a mystery."""
        with override_settings(CREDENTIALS_ENCRYPTION_KEY="not-a-fernet-key"):
            with self.assertRaises(secrets.EncryptionUnavailable):
                secrets.encrypt("sk-secret")


@override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY, EMBEDDING_API_KEY="shared-key")
class CredentialPrecedenceTests(TestCase):
    """Which credential a collection ends up sending."""

    def setUp(self):
        """Register a collection served by an endpoint."""
        self.collection = Collection.objects.create(
            name="remote-model",
            provider=EmbeddingProvider.API,
            base_url="https://endpoint.example/v1",
            model_name="some-model",
            vector_size=384,
        )

    def test_a_stored_credential_is_used(self):
        """It is the one somebody most recently said this collection should use."""
        self.collection.encrypted_api_key = secrets.encrypt("stored-key")
        self.assertEqual(get_api_key(self.collection), "stored-key")

    def test_a_stored_credential_beats_the_shared_one(self):
        """Two collections at two providers must not swap credentials."""
        self.collection.encrypted_api_key = secrets.encrypt("stored-key")
        self.assertNotEqual(get_api_key(self.collection), "shared-key")

    def test_a_named_environment_credential_is_used_when_nothing_is_stored(self):
        """The way keys were configured before this has to keep working."""
        with patch.dict("os.environ", {"EMBEDDING_API_KEY_REMOTE_MODEL": "env-key"}):
            self.assertEqual(get_api_key(self.collection), "env-key")

    def test_a_stored_credential_beats_the_named_environment_one(self):
        """Whatever was typed into the panel last is the current intent."""
        self.collection.encrypted_api_key = secrets.encrypt("stored-key")
        with patch.dict("os.environ", {"EMBEDDING_API_KEY_REMOTE_MODEL": "env-key"}):
            self.assertEqual(get_api_key(self.collection), "stored-key")

    def test_the_shared_credential_is_the_last_resort(self):
        """One provider and one key is the common case and must stay simple."""
        self.assertEqual(get_api_key(self.collection), "shared-key")


@override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY)
class CollectionCredentialEndpointTests(TestCase):
    """What the panel may do with a credential, and what it may never see."""

    def setUp(self):
        """Sign in as the owner."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)

    def register(self, **extra):
        """Register a collection served by an endpoint."""
        payload = {
            "name": "remote",
            "provider": "api",
            "base_url": "https://endpoint.example/v1",
            "model_name": "some-model",
            "vector_size": 384,
        }
        payload.update(extra)
        return self.client.post(
            "/api/collections/", payload, content_type="application/json", secure=True
        )

    def test_a_credential_can_be_saved_with_the_collection(self):
        """Pasting the key into the form is the whole point of this."""
        self.assertEqual(self.register(api_key="sk-typed-in").status_code, 201)
        self.assertEqual(get_api_key(Collection.objects.get(name="remote")), "sk-typed-in")

    def test_the_credential_never_comes_back_in_a_reply(self):
        """A key read back would land in a browser, a cache and a log."""
        body = self.register(api_key="sk-typed-in").json()
        self.assertNotIn("api_key", body)
        self.assertNotIn("sk-typed-in", json.dumps(body))

    def test_the_reply_says_whether_a_credential_is_held(self):
        """The panel has to show a key is set without ever showing the key."""
        self.assertTrue(self.register(api_key="sk-typed-in").json()["has_api_key"])

    def test_a_collection_saved_without_one_says_so(self):
        """A local model needs no key, and the form must not imply otherwise."""
        self.assertFalse(self.register().json()["has_api_key"])

    def test_a_credential_is_not_stored_in_the_clear(self):
        """The row is readable from the database, which is why it is encrypted."""
        self.register(api_key="sk-typed-in")
        self.assertNotIn("sk-typed-in", Collection.objects.get(name="remote").encrypted_api_key)

    def test_a_credential_can_be_replaced_afterwards(self):
        """Rotating a provider key must not mean registering the model again."""
        collection = Collection.objects.get(pk=self.register(api_key="old").json()["collection_id"])
        self.client.patch(
            f"/api/collections/{collection.pk}/",
            {"api_key": "new"},
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(get_api_key(Collection.objects.get(pk=collection.pk)), "new")

    def test_an_empty_credential_clears_the_stored_one(self):
        """Moving a collection back to a key in the environment has to be possible."""
        collection = Collection.objects.get(pk=self.register(api_key="old").json()["collection_id"])
        self.client.patch(
            f"/api/collections/{collection.pk}/",
            {"api_key": ""},
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(Collection.objects.get(pk=collection.pk).encrypted_api_key, "")

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=None)
    def test_an_instance_that_cannot_encrypt_refuses_and_explains(self):
        """Silently dropping the key would leave a collection that cannot embed."""
        response = self.register(api_key="sk-typed-in")
        self.assertEqual(response.status_code, 400)
        self.assertIn("CREDENTIALS_ENCRYPTION_KEY", response.json()["api_key"][0])


class CatalogueTests(TestCase):
    """The list of endpoints the panel offers as a starting point."""

    def test_the_shipped_catalogue_loads(self):
        """A list nobody can read leaves the panel with an empty selector."""
        self.assertTrue(providers.catalogue())

    def test_every_entry_carries_what_the_form_needs(self):
        """An entry missing its URL saves nobody any typing."""
        for provider in providers.catalogue():
            self.assertTrue(provider["base_url"].startswith("http"))
            self.assertTrue(provider["label"])

    @override_settings(PROVIDER_CATALOGUE="/nowhere/at/all.json")
    def test_a_catalogue_that_cannot_be_read_leaves_the_form_usable(self):
        """Typing the endpoint by hand is always possible, so this is not fatal."""
        self.assertEqual(providers.catalogue(), [])

    def test_a_name_that_reads_like_an_embedding_model_is_marked(self):
        """A list of two hundred chat models buries the three that are wanted."""
        self.assertTrue(providers.looks_like_embedding("text-embedding-3-small"))
        self.assertFalse(providers.looks_like_embedding("gpt-4o"))


class EndpointQuestionTests(TestCase):
    """Asking an endpoint what it serves, before anything is saved."""

    def setUp(self):
        """Sign in as the owner."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)

    def answer(self, payload, status_code=200):
        """Build an httpx response the way the endpoint would."""
        request = httpx.Request("GET", "https://endpoint.example/v1/models")
        return httpx.Response(status_code, json=payload, request=request)

    def ask_models(self, **extra):
        """Ask the panel route for the models of an endpoint."""
        payload = {"base_url": "https://endpoint.example/v1"}
        payload.update(extra)
        return self.client.post(
            "/api/providers/models/", payload, content_type="application/json", secure=True
        )

    def test_the_models_of_an_endpoint_are_listed(self):
        """Choosing a model from a list beats typing its name from memory."""
        with patch(
            "httpx.get",
            return_value=self.answer({"data": [{"id": "text-embedding-3-small"}]}),
        ):
            response = self.ask_models()
        self.assertEqual(response.json()["models"][0]["id"], "text-embedding-3-small")

    def test_an_endpoint_serving_one_model_leaves_the_form_usable(self):
        """Most self-hosted servers have one model and no list to give.

        Answering that with a failure would put a red box in front of a form
        that is perfectly fine to fill in by hand, which is how a working
        endpoint gets abandoned as broken.
        """
        request = httpx.Request("GET", "https://endpoint.example/v1/models")
        answer = httpx.Response(404, json={"error": "not found"}, request=request)
        with patch("httpx.get", return_value=answer):
            response = self.ask_models()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["listing_supported"])

    def test_an_endpoint_refusing_the_credential_is_reported_as_a_failure(self):
        """A rejected key is a thing to correct, not an endpoint without a list."""
        request = httpx.Request("GET", "https://endpoint.example/v1/models")
        answer = httpx.Response(401, json={"error": "bad key"}, request=request)
        with patch("httpx.get", return_value=answer):
            self.assertEqual(self.ask_models().status_code, 503)

    def test_an_endpoint_that_cannot_be_reached_is_reported_as_such(self):
        """A mistyped URL has to be visible while the form is still open."""
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            self.assertEqual(self.ask_models().status_code, 503)

    def test_an_endpoint_that_answers_with_nonsense_is_reported_as_such(self):
        """A URL that serves something else is as wrong as one that serves nothing."""
        with patch("httpx.get", return_value=self.answer({"nothing": "useful"})):
            self.assertEqual(self.ask_models().status_code, 503)

    def test_the_width_of_a_model_is_measured_rather_than_typed(self):
        """It is the one field an owner cannot guess and the one that ruins a collection."""
        request = httpx.Request("POST", "https://endpoint.example/v1/embeddings")
        answer = httpx.Response(200, json={"data": [{"embedding": [0.0] * 768}]}, request=request)
        with patch("httpx.post", return_value=answer):
            response = self.client.post(
                "/api/providers/probe/",
                {"base_url": "https://endpoint.example/v1", "model_name": "some-model"},
                content_type="application/json",
                secure=True,
            )
        self.assertEqual(response.json()["vector_size"], 768)

    @override_settings(CREDENTIALS_ENCRYPTION_KEY=KEY)
    def test_a_saved_collection_lends_its_credential(self):
        """Changing a model must not mean typing a key that is already stored."""
        collection = Collection.objects.create(
            name="remote",
            provider=EmbeddingProvider.API,
            base_url="https://endpoint.example/v1",
            model_name="some-model",
            vector_size=384,
            encrypted_api_key=secrets.encrypt("stored-key"),
        )
        with patch("httpx.get", return_value=self.answer({"data": []})) as sent:
            self.ask_models(collection=str(collection.pk))
        self.assertEqual(sent.call_args.kwargs["headers"]["Authorization"], "Bearer stored-key")

    def test_a_key_typed_into_the_form_is_the_one_tried(self):
        """The point of the button is to try the key in front of you."""
        with patch("httpx.get", return_value=self.answer({"data": []})) as sent:
            self.ask_models(api_key="sk-being-tried")
        self.assertEqual(sent.call_args.kwargs["headers"]["Authorization"], "Bearer sk-being-tried")

    def test_an_agent_cannot_ask_anything_of_an_endpoint(self):
        """These routes spend the owner's credentials and reach out of the network."""
        self.client.logout()
        self.assertEqual(self.ask_models().status_code, 401)

    def test_the_catalogue_is_the_owners(self):
        """It names the endpoints this instance is configured to talk to."""
        self.client.logout()
        self.assertEqual(self.client.get("/api/providers/", secure=True).status_code, 401)


class ModelFilteringTests(TestCase):
    """Which of an endpoint's models are put in front of the owner."""

    def setUp(self):
        """Sign in as the owner."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)

    def served(self, names):
        """Build the answer an endpoint gives when asked for its models."""
        request = httpx.Request("GET", "https://endpoint.example/v1/models")
        return httpx.Response(
            200, json={"data": [{"id": name} for name in names]}, request=request
        )

    def ask(self, names, **extra):
        """Ask the panel route what one endpoint offers."""
        payload = {"base_url": "https://endpoint.example/v1"}
        payload.update(extra)
        with patch("httpx.get", return_value=self.served(names)):
            response = self.client.post(
                "/api/providers/models/", payload, content_type="application/json", secure=True
            )
        return response.json()

    def offered(self, names, **extra):
        """Return just the model identifiers the panel would show."""
        return [model["id"] for model in self.ask(names, **extra)["models"]]

    def test_a_chat_model_is_not_offered(self):
        """Registering one makes a collection that can never index anything."""
        offered = self.offered(["gpt-4o", "text-embedding-3-small"], provider="openai")
        self.assertEqual(offered, ["text-embedding-3-small"])

    def test_a_reranker_is_never_offered(self):
        """A reranker scores a pair of texts and returns no vector at all."""
        offered = self.offered(["voyage-3-large", "voyage-rerank-2"], provider="voyage")
        self.assertEqual(offered, ["voyage-3-large"])

    def test_a_provider_naming_its_models_its_own_way_is_understood(self):
        """Not every embedding model has the word embedding in its name."""
        self.assertEqual(
            self.offered(["voyage-3.5", "voyage-code-3"], provider="voyage"),
            ["voyage-3.5", "voyage-code-3"],
        )

    def test_the_reply_says_how_many_were_left_out(self):
        """A list quietly shorter than the provider's is a list nobody trusts."""
        answer = self.ask(["gpt-4o", "o1-preview", "text-embedding-3-small"], provider="openai")
        self.assertEqual(answer["hidden"], 2)
        self.assertTrue(answer["filtered"])

    def test_everything_can_still_be_asked_for(self):
        """A model whose name gives nothing away has to be reachable."""
        answer = self.ask(["gpt-4o", "text-embedding-3-small"], provider="openai", include_all=True)
        self.assertEqual(len(answer["models"]), 2)
        self.assertFalse(answer["filtered"])

    def test_a_list_with_nothing_recognisable_is_offered_whole(self):
        """An empty list is worse than the mistake the filter set out to stop."""
        answer = self.ask(["model-one", "model-two"], provider="openai")
        self.assertEqual(len(answer["models"]), 2)
        self.assertFalse(answer["filtered"])
        self.assertIn("detail", answer)

    def test_an_endpoint_nobody_catalogued_is_guessed_at(self):
        """A custom endpoint is the common case and still deserves the filter."""
        offered = self.offered(["llama3.2", "nomic-embed-text", "bge-m3"])
        self.assertEqual(offered, ["bge-m3", "nomic-embed-text"])

    def test_a_broken_pattern_hides_nothing_rather_than_failing(self):
        """A catalogue somebody edited by hand must not break the form."""
        self.assertFalse(providers.looks_like_embedding("text-embedding-3-small", "([unclosed"))
