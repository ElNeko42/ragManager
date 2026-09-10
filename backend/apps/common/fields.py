"""Serializer fields shared by more than one application."""

from rest_framework import serializers
from rest_framework.fields import empty


class OptionalUUIDField(serializers.UUIDField):
    """An identifier a caller may leave out, or send empty.

    A panel building a query string writes the parameter whether or not it
    holds anything, so an empty value has to mean the filter was not asked for
    rather than an identifier that fails to parse. A value that is present and
    malformed is still refused, which is the whole point of validating it:
    left to the query layer it surfaces as an unhandled error and a 500.
    """

    def run_validation(self, data=empty):
        """Treat an empty value as absent and validate anything else."""
        if data == "":
            return None
        return super().run_validation(data)
