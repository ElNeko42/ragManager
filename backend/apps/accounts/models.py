"""The single owner of a ragManager instance."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Creates the owner account and enforces that there is only one."""

    use_in_migrations = True

    def create_user(self, email, password=None):
        """Create the owner account.

        Refuses to create a second account: this release is single owner and
        the multi user model is a later milestone. Returns the saved user.
        """
        if not email:
            raise ValueError("An email address is required")
        if self.exists():
            raise ValueError("This instance already has an owner")
        user = self.model(email=self.normalize_email(email).lower())
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create the owner account through the standard Django command.

        There are no roles in this release, so a superuser is just the owner.
        Returns the saved user.
        """
        return self.create_user(email=email, password=password)


class User(AbstractBaseUser):
    """A person who signs in to the management panel."""

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        """Return the email address used to sign in."""
        return self.email

    @property
    def is_staff(self):
        """Report whether the account may open the Django admin.

        The owner is the only account, so it always may.
        """
        return True

    def has_perm(self, perm, obj=None):
        """Report whether the account holds a given permission.

        There are no roles in this release, so the owner holds all of them.
        """
        return True

    def has_module_perms(self, app_label):
        """Report whether the account may reach a given application.

        There are no roles in this release, so the owner may reach all of them.
        """
        return True
