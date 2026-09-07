"""Session endpoints used by the management panel."""

from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.accounts.permissions import IsOwner
from apps.accounts.serializers import LoginSerializer, UserSerializer


class LoginThrottle(AnonRateThrottle):
    """Caps how often one address may try to sign in.

    Scoped rather than global so that a burst of failed logins cannot exhaust
    the allowance of the rest of the API.
    """

    scope = "login"


def csrf_required(view):
    """Put a REST framework view back under CSRF checking.

    api_view marks whatever it wraps as csrf_exempt, and both the middleware
    and csrf_protect honour that flag, so a login endpoint left as it comes
    accepts cross site posts. Clearing the flag hands the view back to
    CsrfViewMiddleware. Returns the same view.
    """
    view.csrf_exempt = False
    return view


@csrf_required
@sensitive_post_parameters("password")
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@sensitive_variables()
def login_view(request):
    """Open a browser session for the owner.

    Takes an email and a password. Returns the signed in user, or 401 with a
    single message that does not reveal whether the address exists.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data["email"],
        password=serializer.validated_data["password"],
    )
    if user is None:
        return Response(
            {"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
        )
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsOwner])
def logout_view(request):
    """Close the browser session of the owner.

    Returns 204 once the session cookie has been invalidated.
    """
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsOwner])
def session_view(request):
    """Return the owner behind the current session, or 403 when there is none."""
    return Response(UserSerializer(request.user).data)


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_view(request):
    """Hand the panel a CSRF cookie before it submits the login form.

    Returns 204; the value travels in the csrftoken cookie.
    """
    return Response(status=status.HTTP_204_NO_CONTENT)
