"""Routes for the owner session endpoints."""

from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("csrf/", views.csrf_view, name="auth-csrf"),
    path("login/", views.login_view, name="auth-login"),
    path("logout/", views.logout_view, name="auth-logout"),
    path("session/", views.session_view, name="auth-session"),
    path("account/", views.account_view, name="auth-account"),
]
