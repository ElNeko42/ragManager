"""Reachability probes for every backing service of the stack."""

import boto3
import redis
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from qdrant_client import QdrantClient


def check_postgres():
    """Verify the relational database answers a trivial query.

    Returns a (healthy, detail) tuple where detail holds the error text on
    failure and None on success.
    """
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        return True, None
    except Exception as error:
        return False, str(error)


def check_redis():
    """Verify the Celery broker answers a ping.

    Returns a (healthy, detail) tuple where detail holds the error text on
    failure and None on success.
    """
    try:
        redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2).ping()
        return True, None
    except Exception as error:
        return False, str(error)


def check_qdrant():
    """Verify the vector database lists its collections.

    Returns a (healthy, detail) tuple where detail holds the error text on
    failure and None on success.
    """
    try:
        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=2)
        client.get_collections()
        return True, None
    except Exception as error:
        return False, str(error)


def check_object_storage():
    """Verify the configured bucket exists and is reachable.

    Returns a (healthy, detail) tuple where detail holds the error text on
    failure and None on success.
    """
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return True, None
    except (BotoCoreError, ClientError) as error:
        return False, str(error)


def health(request):
    """Report whether every backing service answers.

    Responds with 200 when all services are reachable and 503 as soon as one
    of them is not, listing the outcome of each individual probe. The reason a
    probe failed is added only for a signed in owner: the text a driver
    returns names hosts, users and endpoints, which is far more than an
    anonymous caller needs in order to learn that something is down.
    """
    probes = {
        "postgres": check_postgres(),
        "redis": check_redis(),
        "qdrant": check_qdrant(),
        "object_storage": check_object_storage(),
    }
    trusted = getattr(request, "user", None) is not None and request.user.is_authenticated
    services = {
        name: {"healthy": healthy, "detail": detail} if trusted else {"healthy": healthy}
        for name, (healthy, detail) in probes.items()
    }
    healthy = all(service["healthy"] for service in services.values())
    return JsonResponse(
        {"healthy": healthy, "services": services},
        status=200 if healthy else 503,
    )
