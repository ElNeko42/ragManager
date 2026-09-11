"""Tests for the authorization flow: what it grants and what it refuses."""

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import Agent, AgentToken
from apps.oauth import tokens
from apps.oauth.models import AuthorizationCode, OAuthClient, RefreshToken

VERIFIER = "a-verifier-long-enough-to-be-worth-something-43chars"
REDIRECT = "https://claude.example/callback"


def challenge_for(verifier):
    """Derive the proof key challenge a client would publish."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class MetadataTests(TestCase):
    """What a client reads before it knows how to ask for anything."""

    def test_the_mcp_endpoint_says_where_to_get_a_token(self):
        """A client refused with no hint has nowhere to go and gives up."""
        answer = self.client.post(
            "/mcp/", "{}", content_type="application/json", secure=True
        )
        self.assertEqual(answer.status_code, 401)
        self.assertIn("resource_metadata=", answer["WWW-Authenticate"])

    def test_the_resource_document_names_an_authorization_server(self):
        """The specification requires at least one, and it is the whole link."""
        body = self.client.get("/.well-known/oauth-protected-resource", secure=True).json()
        self.assertTrue(body["authorization_servers"])

    def test_the_resource_document_names_the_mcp_endpoint(self):
        """Tokens are bound to this, so it has to be the address agents use."""
        body = self.client.get("/.well-known/oauth-protected-resource", secure=True).json()
        self.assertTrue(body["resource"].endswith("/mcp"))

    def test_the_path_suffixed_document_answers_too(self):
        """Clients derive that address from the endpoint path, and some use it."""
        self.assertEqual(
            self.client.get("/.well-known/oauth-protected-resource/mcp", secure=True).status_code,
            200,
        )

    def test_the_server_document_offers_only_the_strong_proof_key(self):
        """The plain method proves nothing to anyone who saw the request."""
        body = self.client.get("/.well-known/oauth-authorization-server", secure=True).json()
        self.assertEqual(body["code_challenge_methods_supported"], ["S256"])

    def test_the_server_document_names_its_three_endpoints(self):
        """A client reads these rather than guessing at paths."""
        body = self.client.get("/.well-known/oauth-authorization-server", secure=True).json()
        for field in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
            self.assertTrue(body[field].startswith("http"))


class RegistrationTests(TestCase):
    """Obtaining an identity without anybody typing one in."""

    def register(self, **extra):
        """Register a client the way a connector would."""
        payload = {"client_name": "Claude", "redirect_uris": [REDIRECT]}
        payload.update(extra)
        return self.client.post(
            reverse("oauth-register"),
            json.dumps(payload),
            content_type="application/json",
            secure=True,
        )

    def test_a_client_can_register_itself(self):
        """Without this, connecting means the owner registering clients by hand."""
        self.assertEqual(self.register().status_code, 201)

    def test_registering_grants_nothing(self):
        """A client holds no access until the owner approves it against an agent."""
        self.register()
        self.assertEqual(AgentToken.objects.count(), 0)

    def test_a_public_client_gets_no_secret(self):
        """A secret a public client cannot keep is a secret in a config file."""
        self.assertNotIn("client_secret", self.register().json())

    def test_a_confidential_client_gets_one(self):
        """A server side client can keep one, and proves itself with it."""
        answer = self.register(token_endpoint_auth_method="client_secret_post")
        self.assertIn("client_secret", answer.json())

    def test_a_redirect_that_is_not_encrypted_is_refused(self):
        """The authorization code travels back through that address."""
        self.assertEqual(self.register(redirect_uris=["http://evil.example/cb"]).status_code, 400)

    def test_a_loopback_redirect_is_allowed(self):
        """A client on the user's own machine has nowhere else to listen."""
        self.assertEqual(self.register(redirect_uris=["http://127.0.0.1:7777/cb"]).status_code, 201)

    def test_registering_without_a_redirect_is_refused(self):
        """There would be nowhere to send the answer."""
        self.assertEqual(self.register(redirect_uris=[]).status_code, 400)


class AuthorizeTests(TestCase):
    """The screen where the owner decides, and what it refuses to show."""

    def setUp(self):
        """Register a client and an agent, and sign the owner in."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.agent = Agent.objects.create(name="hermes")
        self.client_record = OAuthClient.objects.create(
            name="Claude", redirect_uris=[REDIRECT], registered_dynamically=True
        )
        self.client.force_login(self.owner)

    def ask(self, **extra):
        """Open the approval screen the way a client would."""
        query = {
            "client_id": str(self.client_record.client_id),
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": challenge_for(VERIFIER),
            "code_challenge_method": "S256",
            "state": "xyz",
        }
        query.update(extra)
        return self.client.get(reverse("oauth-authorize"), query, secure=True)

    def approve(self, **extra):
        """Answer the screen, approving as the agent."""
        payload = {
            "client_id": str(self.client_record.client_id),
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": challenge_for(VERIFIER),
            "code_challenge_method": "S256",
            "state": "xyz",
            "agent": str(self.agent.pk),
            "decision": "approve",
        }
        payload.update(extra)
        return self.client.post(reverse("oauth-authorize"), payload, secure=True)

    def test_the_owner_is_asked_before_anything_is_granted(self):
        """Access to a private store is not something to hand over silently."""
        self.assertEqual(self.ask().status_code, 200)

    def test_the_screen_names_the_client_asking(self):
        """Approving something unnamed is approving anything."""
        self.assertContains(self.ask(), "Claude")

    def test_a_visitor_who_is_not_the_owner_is_sent_to_sign_in(self):
        """Anyone who could approve without signing in could grant themselves access."""
        self.client.logout()
        answer = self.ask()
        self.assertEqual(answer.status_code, 302)
        self.assertIn("next=", answer["Location"])

    def test_an_unregistered_redirect_is_never_redirected_to(self):
        """Sending the browser there is the attack this check exists to stop."""
        answer = self.ask(redirect_uri="https://attacker.example/steal")
        self.assertEqual(answer.status_code, 400)
        self.assertNotIn("Location", answer)

    def test_an_unknown_client_is_refused_on_the_page(self):
        """There is no address to send an answer to that can be trusted."""
        self.assertEqual(self.ask(client_id="6f1d5a7e-8c3b-4f2a-9d61-2b7e4c0a8f35").status_code, 400)

    def test_a_request_without_a_proof_key_is_refused(self):
        """Without it a stolen code can be redeemed by whoever stole it."""
        self.assertEqual(self.ask(code_challenge="").status_code, 400)

    def test_the_weak_proof_key_method_is_refused(self):
        """The plain method is no protection against anyone who saw the request."""
        self.assertEqual(self.ask(code_challenge_method="plain").status_code, 400)

    def test_a_token_for_another_resource_is_refused(self):
        """This server has no business issuing credentials for somewhere else."""
        self.assertEqual(self.ask(resource="https://elsewhere.example/mcp").status_code, 400)

    def test_approving_sends_a_code_back_to_the_client(self):
        """That code is the whole result of the screen."""
        answer = self.approve()
        self.assertEqual(answer.status_code, 302)
        self.assertIn("code=", answer["Location"])

    def test_the_state_comes_back_untouched(self):
        """The client checks it to know the answer belongs to its own request."""
        parameters = parse_qs(urlparse(self.approve()["Location"]).query)
        self.assertEqual(parameters["state"], ["xyz"])

    def test_refusing_says_so_rather_than_leaving_the_client_waiting(self):
        """A connector told nothing sits there as though it were still deciding."""
        answer = self.approve(decision="deny")
        self.assertIn("error=access_denied", answer["Location"])

    def test_the_code_is_bound_to_the_agent_the_owner_chose(self):
        """Choosing an agent is choosing what the connector will be able to read."""
        self.approve()
        self.assertEqual(AuthorizationCode.objects.first().agent, self.agent)

    def test_only_the_hash_of_the_code_is_kept(self):
        """It travels through a redirect, so the row must not be replayable."""
        code = parse_qs(urlparse(self.approve()["Location"]).query)["code"][0]
        self.assertNotIn(code, AuthorizationCode.objects.first().code_hash)


class TokenTests(TestCase):
    """Exchanging an approval for a credential, and the ways that can go wrong."""

    def setUp(self):
        """Approve a client so that a code is waiting to be exchanged."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.agent = Agent.objects.create(name="hermes")
        self.client_record = OAuthClient.objects.create(
            name="Claude", redirect_uris=[REDIRECT], registered_dynamically=True
        )
        self.client.force_login(self.owner)
        self.code = self.fresh_code()
        self.client.logout()

    def fresh_code(self):
        """Run the approval screen and return the code it handed back."""
        answer = self.client.post(
            reverse("oauth-authorize"),
            {
                "client_id": str(self.client_record.client_id),
                "redirect_uri": REDIRECT,
                "response_type": "code",
                "code_challenge": challenge_for(VERIFIER),
                "code_challenge_method": "S256",
                "agent": str(self.agent.pk),
                "decision": "approve",
            },
            secure=True,
        )
        return parse_qs(urlparse(answer["Location"]).query)["code"][0]

    def exchange(self, **extra):
        """Ask for a token the way a client would."""
        payload = {
            "grant_type": "authorization_code",
            "code": self.code,
            "code_verifier": VERIFIER,
            "redirect_uri": REDIRECT,
            "client_id": str(self.client_record.client_id),
        }
        payload.update(extra)
        return self.client.post(reverse("oauth-token"), payload, secure=True)

    def test_a_code_becomes_a_token(self):
        """This is the point of the whole flow."""
        body = self.exchange().json()
        self.assertEqual(body["token_type"], "Bearer")
        self.assertTrue(body["access_token"])

    def test_the_token_opens_the_mcp_endpoint(self):
        """A credential that does not work is an elaborate way to fail."""
        access = self.exchange().json()["access_token"]
        answer = self.client.post(
            "/mcp/",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(answer.status_code, 200)

    def test_the_token_acts_as_the_agent_the_owner_chose(self):
        """Everything downstream reads permissions from that identity."""
        self.exchange()
        self.assertEqual(AgentToken.objects.first().agent, self.agent)

    def test_the_token_expires_on_its_own(self):
        """A connector can renew, so a long lived credential buys nothing."""
        self.exchange()
        self.assertIsNotNone(AgentToken.objects.first().expires_at)

    def test_a_refresh_token_comes_with_it(self):
        """Without one the connector would have to ask the owner again hourly."""
        self.assertIn("refresh_token", self.exchange().json())

    def test_the_wrong_proof_key_is_refused(self):
        """Whoever stole the code does not have the verifier."""
        answer = self.exchange(code_verifier="not-the-verifier-that-was-used-here")
        self.assertEqual(answer.status_code, 400)
        self.assertEqual(answer.json()["error"], "invalid_grant")

    def test_a_code_cannot_be_used_twice(self):
        """A second exchange means somebody else is holding it."""
        self.exchange()
        self.assertEqual(self.exchange().status_code, 400)

    def test_reusing_a_code_withdraws_what_it_produced(self):
        """There is no telling the client from the thief, so neither keeps it."""
        access = self.exchange().json()["access_token"]
        self.exchange()
        stored = AgentToken.objects.get(token_hash__isnull=False)
        self.assertFalse(stored.is_valid())
        self.assertTrue(access)

    def test_a_different_redirect_at_exchange_time_is_refused(self):
        """The address is part of what was approved, not a free field."""
        self.assertEqual(self.exchange(redirect_uri="https://elsewhere.example/cb").status_code, 400)

    def test_another_client_cannot_redeem_the_code(self):
        """A code belongs to the client the owner saw named on the screen."""
        other = OAuthClient.objects.create(name="Other", redirect_uris=[REDIRECT])
        answer = self.exchange(client_id=str(other.client_id))
        self.assertEqual(answer.status_code, 400)

    def test_an_expired_code_is_refused(self):
        """It travels through a browser, so its window is the shortest here."""
        record = AuthorizationCode.objects.first()
        record.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        record.save(update_fields=["expires_at"])
        self.assertEqual(self.exchange().status_code, 400)

    def test_a_confidential_client_must_prove_itself(self):
        """A secret that is never checked is not a secret."""
        secret = tokens.mint()
        self.client_record.secret_hash = tokens.digest(secret)
        self.client_record.save(update_fields=["secret_hash"])
        self.assertEqual(self.exchange().status_code, 401)
        self.assertEqual(self.exchange(client_secret=secret).status_code, 200)

    def test_an_unknown_grant_is_refused(self):
        """Only the two grants this server offers are answered."""
        answer = self.exchange(grant_type="password")
        self.assertEqual(answer.json()["error"], "unsupported_grant_type")


class RefreshTests(TestCase):
    """Renewing a credential, and noticing when one has been copied."""

    def setUp(self):
        """Get through the flow once, so a refresh token exists."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.agent = Agent.objects.create(name="hermes")
        self.client_record = OAuthClient.objects.create(
            name="Claude", redirect_uris=[REDIRECT], registered_dynamically=True
        )
        self.client.force_login(self.owner)
        answer = self.client.post(
            reverse("oauth-authorize"),
            {
                "client_id": str(self.client_record.client_id),
                "redirect_uri": REDIRECT,
                "response_type": "code",
                "code_challenge": challenge_for(VERIFIER),
                "code_challenge_method": "S256",
                "agent": str(self.agent.pk),
                "decision": "approve",
            },
            secure=True,
        )
        self.client.logout()
        code = parse_qs(urlparse(answer["Location"]).query)["code"][0]
        body = self.client.post(
            reverse("oauth-token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": VERIFIER,
                "redirect_uri": REDIRECT,
                "client_id": str(self.client_record.client_id),
            },
            secure=True,
        ).json()
        self.refresh = body["refresh_token"]
        self.access = body["access_token"]

    def renew(self, refresh=None):
        """Exchange a refresh token for a new pair."""
        return self.client.post(
            reverse("oauth-token"),
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh or self.refresh,
                "client_id": str(self.client_record.client_id),
            },
            secure=True,
        )

    def test_a_refresh_token_yields_a_new_pair(self):
        """A connector renews on its own rather than asking the owner again."""
        body = self.renew().json()
        self.assertTrue(body["access_token"])
        self.assertNotEqual(body["refresh_token"], self.refresh)

    def test_the_old_access_token_stops_working(self):
        """Two live credentials from one renewal doubles what a leak costs."""
        self.renew()
        answer = self.client.post(
            "/mcp/",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(answer.status_code, 401)

    def test_a_refresh_token_cannot_be_used_twice(self):
        """Rotation is what makes a copied token detectable at all."""
        self.renew()
        self.assertEqual(self.renew().status_code, 400)

    def test_reusing_one_withdraws_the_whole_chain(self):
        """Whoever has the copy must not be left holding a working credential."""
        second = self.renew().json()["refresh_token"]
        self.renew()
        self.assertEqual(self.renew(second).status_code, 400)
        self.assertFalse(any(token.is_valid() for token in AgentToken.objects.all()))

    def test_another_client_cannot_renew_with_it(self):
        """A refresh token belongs to the client it was issued to."""
        other = OAuthClient.objects.create(name="Other", redirect_uris=[REDIRECT])
        answer = self.client.post(
            reverse("oauth-token"),
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh,
                "client_id": str(other.client_id),
            },
            secure=True,
        )
        self.assertEqual(answer.status_code, 400)

    def test_only_hashes_of_refresh_tokens_are_kept(self):
        """The database must not hold something that opens the store."""
        self.assertNotIn(self.refresh, RefreshToken.objects.first().token_hash)


class AudienceTests(TestCase):
    """Where a token approved for the MCP endpoint may and may not be used."""

    def setUp(self):
        """Mint one token through the flow and one the way the panel does."""
        from apps.agents.tokens import issue_token
        from apps.oauth.service import mint_pair

        self.agent = Agent.objects.create(name="hermes")
        self.client_record = OAuthClient.objects.create(name="Claude", redirect_uris=[REDIRECT])
        self.connector, _ = mint_pair(
            self.client_record, self.agent, "https://testserver/mcp"
        )
        self.by_hand = issue_token(self.agent)[1]

    def reach(self, path, token):
        """Call an endpoint with one of the two tokens."""
        return self.client.post(
            path,
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_a_connector_token_opens_the_endpoint_it_was_approved_for(self):
        """That is what the owner approved it for."""
        self.assertEqual(self.reach("/mcp/", self.connector).status_code, 200)

    def test_a_connector_token_is_refused_elsewhere(self):
        """Replaying it against another resource is what binding it prevents."""
        self.assertEqual(self.reach("/api/search/", self.connector).status_code, 401)

    def test_a_token_the_owner_issued_is_not_held_to_an_audience(self):
        """It was handed over for the agent to use wherever it goes."""
        self.assertEqual(self.reach("/mcp/", self.by_hand).status_code, 200)


class SignInDetourTests(TestCase):
    """What happens when the approval screen is reached by a stranger."""

    def setUp(self):
        """Register a client, with nobody signed in."""
        self.client_record = OAuthClient.objects.create(
            name="Claude", redirect_uris=[REDIRECT], registered_dynamically=True
        )

    def test_the_request_survives_the_detour_through_signing_in(self):
        """Losing the parameters means the connector starts over for nothing."""
        answer = self.client.get(
            reverse("oauth-authorize"),
            {
                "client_id": str(self.client_record.client_id),
                "redirect_uri": REDIRECT,
                "response_type": "code",
                "code_challenge": challenge_for(VERIFIER),
                "code_challenge_method": "S256",
                "state": "xyz",
            },
            secure=True,
        )
        destination = parse_qs(urlparse(answer["Location"]).query)["next"][0]
        self.assertIn("client_id=", destination)
        self.assertIn("code_challenge=", destination)
        self.assertIn("state=xyz", destination)


class RevokingAConnectorTests(TestCase):
    """What revoking a connector's token in the panel has to take with it."""

    def setUp(self):
        """Put a connector through the flow, then sign the owner in."""
        from apps.oauth.service import mint_pair

        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.agent = Agent.objects.create(name="hermes")
        self.client_record = OAuthClient.objects.create(name="Claude", redirect_uris=[REDIRECT])
        self.access, self.refresh = mint_pair(
            self.client_record, self.agent, "https://testserver/mcp"
        )
        self.client.force_login(self.owner)

    def revoke(self):
        """Revoke the connector's token the way the panel does."""
        token = AgentToken.objects.get(audience="https://testserver/mcp")
        return self.client.post(
            f"/api/agents/{self.agent.pk}/tokens/{token.pk}/revoke/", secure=True
        )

    def test_revoking_stops_the_token(self):
        """That is what the button says it does."""
        self.revoke()
        self.assertFalse(AgentToken.objects.first().is_valid())

    def test_revoking_stops_the_renewal_too(self):
        """Otherwise the connector mints another one and carries on."""
        self.revoke()
        self.client.logout()
        answer = self.client.post(
            reverse("oauth-token"),
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh,
                "client_id": str(self.client_record.client_id),
            },
            secure=True,
        )
        self.assertEqual(answer.status_code, 400)

    def test_revoking_a_token_issued_by_hand_still_works(self):
        """Most tokens have no renewal, and that path must not break."""
        from apps.agents.tokens import issue_token

        record, _ = issue_token(self.agent)
        answer = self.client.post(
            f"/api/agents/{self.agent.pk}/tokens/{record.pk}/revoke/", secure=True
        )
        self.assertEqual(answer.status_code, 200)
