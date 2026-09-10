"""Tests for the endpoint that changes the owner's own sign in details."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

CURRENT = "sQ7-forest-lantern"
NEXT = "vK2-harbour-thistle"


class AccountChangeTests(TestCase):
    """What the panel may change about the account, and what it may not."""

    def setUp(self):
        """Sign in as the owner, the way the panel does."""
        self.owner = User.objects.create_user(email="owner@example.com", password=CURRENT)
        self.url = reverse("auth-account")
        self.client.force_login(self.owner)

    def patch(self, **payload):
        """Send a change to the account endpoint as JSON."""
        return self.client.patch(
            self.url, payload, content_type="application/json", secure=True
        )

    def test_the_address_changes_when_the_password_is_right(self):
        """The new address comes back and is what the account signs in with."""
        response = self.patch(current_password=CURRENT, email="Owner@Example.NET")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "owner@example.net")
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "owner@example.net")

    def test_the_password_changes_and_the_session_survives(self):
        """The owner stays signed in, and the old password stops working."""
        response = self.patch(current_password=CURRENT, new_password=NEXT)
        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password(NEXT))
        self.assertEqual(self.client.get(reverse("auth-session"), secure=True).status_code, 200)

    def test_a_wrong_current_password_changes_nothing(self):
        """Refused on the field, not as a session that ended, and nothing moves."""
        response = self.patch(current_password="not-the-password", email="taken@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json())
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "owner@example.com")

    def test_a_weak_password_is_refused_with_a_reason(self):
        """The rejection names the field, so the panel can say what was wrong."""
        response = self.patch(current_password=CURRENT, new_password="12345")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password(CURRENT))

    def test_a_request_that_changes_nothing_is_refused(self):
        """Sending only the current password is a mistake, not a success."""
        self.assertEqual(self.patch(current_password=CURRENT).status_code, 400)

    def test_a_stranger_cannot_reach_the_endpoint(self):
        """With no session there is nothing to change."""
        self.client.logout()
        self.assertIn(
            self.patch(current_password=CURRENT, email="x@example.com").status_code,
            (401, 403),
        )
