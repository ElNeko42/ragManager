"""Tests for agent management, tokens and the address agents connect to."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.agents.models import Agent


class ConnectionAddressTests(TestCase):
    """The address the panel hands to whoever is setting up a client."""

    def setUp(self):
        """Sign in as the owner with one agent registered."""
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="pw-8x-forest"
        )
        self.client.force_login(self.owner)
        self.agent = Agent.objects.create(name="hermes")

    def address(self, **extra):
        """Ask the panel route for the MCP address."""
        return self.client.get("/api/agents/connection/", secure=True, **extra).json()["url"]

    def test_the_address_is_the_mcp_endpoint(self):
        """A client pointed anywhere else is a client that never connects."""
        self.assertTrue(self.address().endswith("/mcp/"))

    def test_the_address_is_absolute(self):
        """It is pasted into a file on another machine, so a path is no use."""
        self.assertTrue(self.address().startswith("http"))

    @override_settings(ALLOWED_HOSTS=["rag.example.com"], USE_X_FORWARDED_HOST=True)
    def test_the_address_is_the_one_agents_can_reach(self):
        """Behind a proxy the container's own name reaches nobody."""
        self.assertEqual(
            self.address(HTTP_X_FORWARDED_HOST="rag.example.com"),
            "https://rag.example.com/mcp/",
        )

    def test_an_agent_cannot_ask_for_it(self):
        """Setting up a client is the owner's job, not an agent's."""
        self.client.logout()
        self.assertEqual(
            self.client.get("/api/agents/connection/", secure=True).status_code, 401
        )
