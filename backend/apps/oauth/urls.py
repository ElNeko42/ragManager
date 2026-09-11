"""Routes of the authorization server."""

from django.urls import path

from apps.oauth import views

urlpatterns = [
    path("authorize/", views.AuthorizeView.as_view(), name="oauth-authorize"),
    path("token/", views.TokenView.as_view(), name="oauth-token"),
    path("register/", views.RegisterView.as_view(), name="oauth-register"),
]
