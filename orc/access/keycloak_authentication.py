from django.http import HttpRequest
from django.contrib.auth.models import User
from rest_framework import authentication
from django.conf import settings
import rest_framework
import jose
import re
import keycloak
from django.core.cache import cache


class KeycloakAuthentication(authentication.BaseAuthentication):
    regex_bearer = re.compile(r"^[Bb]earer (.*)$")

    def __init__(self, *args, **kwargs):
        # Configure client
        self.keycloak = keycloak.KeycloakOpenID(
            server_url=settings.KEYCLOAK_SERVER_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            realm_name=settings.KEYCLOAK_REALM_NAME,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY
        )

        if (cache.get('keycloak_public_key') is None):
            self.public_key = "-----BEGIN PUBLIC KEY-----\n" + \
                self.keycloak.public_key() + "\n-----END PUBLIC KEY-----"
            cache.set('keycloak_public_key', self.public_key, 60 * 60)
        else:
            self.public_key = cache.get('keycloak_public_key')
        self.verify_options = {"verify_signature": True,
                               "verify_aud": False, "verify_exp": True}

    def authenticate(self, request: HttpRequest):
        header_authorization_value = request.headers.get("authorization")
        if not header_authorization_value:
            return None

        match = self.regex_bearer.match(header_authorization_value)
        if not match:
            return None
        raw_jwt = str(match.groups()[-1])

        try:
            token_info = self.keycloak.decode_token(
                raw_jwt, key=self.public_key, options=self.verify_options)
        except jose.exceptions.ExpiredSignatureError as e:
            raise rest_framework.exceptions.AuthenticationFailed(str(e))
        except jose.exceptions.JWTError as e:
            raise rest_framework.exceptions.AuthenticationFailed(str(e))

        try:
            user = User.objects.get(username=token_info['preferred_username'])
        except User.DoesNotExist:
            # Create user if do not exist
            user = User.objects.create_user(
                token_info['preferred_username'], token_info['email'])

        return (user, None)
