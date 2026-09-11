"""Celery application shared by the web and worker entry points."""

import os

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("ragmanager")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_process_init.connect
def warm_up_embeddings(**kwargs):
    """Load the embedding models before the first document arrives.

    The first job after a worker starts would otherwise spend its first ten
    seconds loading the model, which counts against the job's time budget and
    shows the owner a document sitting in processing for no visible reason.
    """
    from apps.ingestion.embeddings import warm_up

    warm_up()
