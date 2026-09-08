"""Tests for how an agent's permissions resolve over the folder tree."""

from django.test import TestCase

from apps.access.models import Permission, PermissionEffect
from apps.access.resolver import resolve_access, resolve_folder_effects
from apps.agents.models import Agent
from apps.drive.models import Collection, Document, Folder

ALLOW = PermissionEffect.ALLOW
DENY = PermissionEffect.DENY


class InheritanceTests(TestCase):
    """Which rule ends up applying to each folder, once inheritance is resolved."""

    def setUp(self):
        """Build a tree with an allow, a deny beneath it and an untouched branch."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.legal = self.make_folder("Legal", self.root)
        self.contracts = self.make_folder("Contracts", self.legal)
        self.private = self.make_folder("Private", self.legal)
        self.public = self.make_folder("Public", self.root)
        self.agent = Agent.objects.create(name="reader")
        Permission.objects.create(agent=self.agent, folder=self.legal, effect=ALLOW)
        Permission.objects.create(agent=self.agent, folder=self.private, effect=DENY)

    def make_folder(self, name, parent):
        """Create a folder under a parent, in the instance's default collection."""
        return Folder.objects.create(name=name, parent=parent, collection=self.collection)

    def effects(self):
        """Resolve the effective rule of every folder for the agent under test."""
        return resolve_folder_effects(self.agent)

    def test_a_folder_with_a_rule_of_its_own_uses_it(self):
        """Legal carries an allow of its own, so nothing else decides for it."""
        self.assertEqual(self.effects()[self.legal.pk], ALLOW)

    def test_a_folder_without_a_rule_inherits_from_its_parent(self):
        """Contracts carries no rule, so it takes the allow that Legal resolved to."""
        self.assertEqual(self.effects()[self.contracts.pk], ALLOW)

    def test_a_deny_on_a_child_beats_an_allow_on_its_parent(self):
        """Private sits inside an allowed folder and still resolves to deny."""
        self.assertEqual(self.effects()[self.private.pk], DENY)

    def test_a_folder_with_no_rule_anywhere_on_its_path_is_denied(self):
        """Public is never named by any rule, so the default of denying applies."""
        self.assertEqual(self.effects()[self.public.pk], DENY)

    def test_the_root_is_denied_when_no_rule_names_it(self):
        """Nothing is readable by default, not even from the top of the tree."""
        self.assertEqual(self.effects()[self.root.pk], DENY)

    def test_removing_a_rule_returns_the_folder_to_what_it_inherits(self):
        """Dropping the deny on Private lets the allow on Legal reach it again."""
        Permission.objects.filter(agent=self.agent, folder=self.private).delete()
        self.assertEqual(self.effects()[self.private.pk], ALLOW)

    def test_an_agent_with_no_rules_at_all_reaches_nothing(self):
        """An agent nobody granted anything to sees every folder as denied."""
        stranger = Agent.objects.create(name="stranger")
        self.assertEqual(set(resolve_folder_effects(stranger).values()), {DENY})
        self.assertEqual(resolve_access(stranger), {})

    def test_deleting_a_folder_removes_the_rules_that_named_it(self):
        """A rule cannot outlive its target and start applying to something else."""
        self.private.delete()
        self.assertFalse(Permission.objects.filter(folder_id=self.private.pk).exists())

    def test_a_folder_unreachable_from_the_root_is_denied(self):
        """A branch detached from the tree resolves to deny rather than to nothing."""
        orphan = Folder.objects.create(
            name="Orphan", parent=self.legal, collection=self.collection
        )
        Folder.objects.filter(pk=orphan.pk).update(parent=orphan)
        self.assertEqual(self.effects()[orphan.pk], DENY)

    def test_a_cycle_in_the_tree_does_not_hang_the_walk(self):
        """A cycle written straight into the table stops the walk instead of looping."""
        first = self.make_folder("First", self.root)
        second = self.make_folder("Second", first)
        Folder.objects.filter(pk=first.pk).update(parent=second)
        self.assertEqual(self.effects()[self.legal.pk], ALLOW)


class SearchScopeTests(TestCase):
    """How resolved permissions turn into the scope the search is given."""

    def setUp(self):
        """Grant a folder, deny a document inside it and allow one outside it."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.open_folder = Folder.objects.create(
            name="Open", parent=self.root, collection=self.collection
        )
        self.closed_folder = Folder.objects.create(
            name="Closed", parent=self.root, collection=self.collection
        )
        self.visible = self.make_document("visible.txt", self.open_folder)
        self.excluded = self.make_document("excluded.txt", self.open_folder)
        self.rescued = self.make_document("rescued.txt", self.closed_folder)
        self.agent = Agent.objects.create(name="reader")
        Permission.objects.create(agent=self.agent, folder=self.open_folder, effect=ALLOW)
        Permission.objects.create(agent=self.agent, document=self.excluded, effect=DENY)
        Permission.objects.create(agent=self.agent, document=self.rescued, effect=ALLOW)

    def make_document(self, name, folder):
        """Register a document in a folder, without storing anything for it."""
        return Document.objects.create(
            folder=folder, name=name, content_type="text/plain", size_bytes=1, storage_key=name
        )

    def scope(self):
        """Return the scope resolved for the agent inside the default collection."""
        return resolve_access(self.agent)[self.collection.pk]

    def test_an_allowed_folder_reaches_the_scope_of_its_own_collection(self):
        """The folders an agent may read are grouped by the collection holding them."""
        self.assertIn(self.open_folder.pk, self.scope()["folders"])

    def test_a_denied_folder_stays_out_of_the_scope(self):
        """A folder nobody granted is absent, not present and filtered later."""
        self.assertNotIn(self.closed_folder.pk, self.scope()["folders"])

    def test_a_document_allowed_inside_a_denied_folder_travels_on_its_own(self):
        """A rule on a document overrides the folder it happens to sit in."""
        self.assertEqual(self.scope()["documents"], [self.rescued.pk])

    def test_a_document_denied_inside_an_allowed_folder_is_carried_as_an_exclusion(self):
        """A deny cannot be resolved away, because its folder still matches."""
        self.assertEqual(self.scope()["denied_documents"], [self.excluded.pk])

    def test_a_collection_nothing_is_allowed_in_is_never_searched(self):
        """Collections the agent cannot reach are absent from the scope entirely."""
        other = Collection.objects.create(
            name="other", provider="local", model_name="m", vector_size=8
        )
        Folder.objects.create(name="Elsewhere", parent=self.root, collection=other)
        self.assertNotIn(other.pk, resolve_access(self.agent))
