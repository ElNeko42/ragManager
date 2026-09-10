"""Serializers for the owner session endpoints."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        """Normalise the submitted address to match how it was stored."""
        return value.lower()


class AccountSerializer(serializers.Serializer):
    """Reads a change to the owner's own sign in details.

    The current password is asked for even when only the address changes: an
    unattended browser is the likeliest way someone else reaches this endpoint,
    and both fields are what signing in depends on.
    """

    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    email = serializers.EmailField(required=False)
    new_password = serializers.CharField(
        required=False, write_only=True, style={"input_type": "password"}
    )

    def validate_current_password(self, value):
        """Check the password the request was made with.

        Refused as a field error rather than as a 401: to the panel a 401 means
        the session ended, and it answers one by returning to the sign in
        screen. A mistyped password in a settings form is a typo, not the end
        of a session. Returns the accepted password.
        """
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("That is not the current password.")
        return value

    def validate_email(self, value):
        """Normalise the submitted address to match how it was stored."""
        return value.lower()

    def validate_new_password(self, value):
        """Hold the new password to the rules the project configured.

        The account is checked against too, so a password that merely repeats
        the owner's own address is refused. Returns the accepted password.
        """
        try:
            validate_password(value, self.context["request"].user)
        except DjangoValidationError as refused:
            raise serializers.ValidationError(list(refused.messages)) from refused
        return value

    def validate(self, attrs):
        """Refuse a request that changes nothing.

        A payload carrying only the current password would answer 200 without
        having done anything, which reads as success. Returns the fields.
        """
        if "email" not in attrs and "new_password" not in attrs:
            raise serializers.ValidationError(
                "Send a new email address, a new password, or both."
            )
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("user_id", "email")
        read_only_fields = fields
