"""Validation helpers shared by more than one application."""

import uuid

from rest_framework import serializers


def parse_uuid(value, field):
    """Read a value that must be an identifier.

    Takes the raw value and the name of the field it came from. Returns the
    identifier. Raises a validation error, which the framework turns into a
    400, rather than letting a malformed value reach the query layer, where
    it surfaces as an unhandled error and a 500.
    """
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        raise serializers.ValidationError({field: "This value must be a valid identifier"})
