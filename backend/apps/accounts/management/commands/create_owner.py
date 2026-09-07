"""Management command that creates the single owner account."""

from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the owner account of this instance"

    def add_arguments(self, parser):
        """Declare the email and password options of the command."""
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", default=None)

    def handle(self, *args, **options):
        """Create the owner account.

        Reads the password from the option or, when absent, prompts for it
        twice without echo. Raises CommandError when the instance already has
        an owner or the password fails Django's validators.
        """
        if User.objects.exists():
            raise CommandError("This instance already has an owner")
        password = options["password"] or self.prompt_for_password()
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages))
        user = User.objects.create_user(email=options["email"], password=password)
        self.stdout.write(self.style.SUCCESS(f"Owner created: {user.email}"))

    def prompt_for_password(self):
        """Ask for the password twice and return it once both entries match.

        Raises CommandError when the two entries differ or the value is empty.
        """
        password = getpass("Password: ")
        if not password:
            raise CommandError("The password cannot be empty")
        if password != getpass("Password (again): "):
            raise CommandError("The two passwords did not match")
        return password
