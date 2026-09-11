"""Management command that throws away what the authorization flow is done with."""

from django.core.management.base import BaseCommand

from apps.oauth.pruning import prune


class Command(BaseCommand):
    help = "Delete expired codes, dead tokens and clients that never completed the flow"

    def handle(self, *args, **options):
        """Prune and say what went.

        The same pruning runs on its own each time a client registers, so this
        is for an instance that wants it on a schedule as well, or for looking
        at what has piled up.
        """
        for kind, count in prune().items():
            self.stdout.write(f"{kind}: {count} removed")
