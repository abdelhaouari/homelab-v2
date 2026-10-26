import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from promotion_api.domain import Actor, Role

ISSUER = os.environ.get(
    "PROMOTION_OIDC_ISSUER",
    "http://localhost:8080/realms/homelab",
)
AUDIENCE = "promotion-api"

JWKS_URL = os.environ.get(
    "PROMOTION_OIDC_JWKS_URL",
    f"{ISSUER}/protocol/openid-connect/certs",
)

bearer = HTTPBearer(auto_error=False)
jwks_client = PyJWKClient(JWKS_URL, timeout=5)


def actor_from_access_token(token: str) -> Actor:
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256":
        raise jwt.InvalidTokenError("Unexpected signing algorithm.")

    if not isinstance(header.get("kid"), str) or not header["kid"]:
        raise jwt.InvalidTokenError("Missing signing key identifier.")

    signing_key = jwks_client.get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={
            "require": ["iss", "aud", "sub", "exp", "iat", "typ"],
        },
    )

    # This application accepts Keycloak bearer access tokens.
    if claims["typ"] != "Bearer":
        raise jwt.InvalidTokenError("Unexpected token type.")

    if not isinstance(claims["sub"], str) or not claims["sub"].strip():
        raise jwt.InvalidTokenError("Invalid subject.")

    if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
        raise jwt.InvalidTokenError("Invalid timestamp types.")

    if claims["exp"] <= claims["iat"]:
        raise jwt.InvalidTokenError("Invalid validity interval.")

    resources = claims.get("resource_access", {})
    if not isinstance(resources, dict):
        raise jwt.InvalidTokenError("Invalid resource access claims.")

    api_access = resources.get(AUDIENCE, {})
    if not isinstance(api_access, dict):
        raise jwt.InvalidTokenError("Invalid API access claims.")

    role_names = api_access.get("roles", [])
    if not isinstance(role_names, list) or not all(
        isinstance(name, str) for name in role_names
    ):
        raise jwt.InvalidTokenError("Invalid roles.")

    known_roles = {role.value: role for role in Role}
    roles = frozenset(known_roles[name] for name in role_names if name in known_roles)

    return Actor(subject=claims["sub"], roles=roles)


def get_current_actor(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
) -> Actor:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return actor_from_access_token(credentials.credentials)
    except PyJWKClientConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable.",
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
