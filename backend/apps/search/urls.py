"""Routes for the search endpoint."""

from django.urls import path

from apps.search import views

urlpatterns = [path("", views.SearchView.as_view(), name="search")]
