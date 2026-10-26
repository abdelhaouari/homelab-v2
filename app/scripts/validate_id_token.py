import base64
import hashlib
import secrets

import jwt
from jwt import PyJWKClient


def validate_id_token(
    id_token: str,
    *,
    issuer: str,
    client_id: str,
    expected_nonce: str,
    access_token: str,
) -> dict:
    header = jwt.get_unverified_header(id_token)

    if header.get("alg") != "RS256":
        raise jwt.InvalidTokenError("Unexpected signing algorithm.")

    if not isinstance(header.get("kid"), str) or not header["kid"]:
        raise jwt.InvalidTokenError("Missing signing key identifier.")

    # The trusted issuer comes from our configuration, not from the token.
    jwks_client = PyJWKClient(
        f"{issuer}/protocol/openid-connect/certs",
        timeout=5,
    )
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=client_id,
        options={
            "require": ["iss", "sub", "aud", "exp", "iat", "nonce"],
            "strict_aud": True,
        },
    )

    if not isinstance(claims["sub"], str) or not claims["sub"].strip():
        raise jwt.InvalidTokenError("Invalid subject.")

    if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
        raise jwt.InvalidTokenError("Invalid timestamp types.")

    if claims["exp"] <= claims["iat"]:
        raise jwt.InvalidTokenError("Invalid validity interval.")

    nonce = claims["nonce"]
    if (
        not isinstance(nonce, str)
        or not expected_nonce
        or not secrets.compare_digest(
            nonce.encode("utf-8"),
            expected_nonce.encode("utf-8"),
        )
    ):
        raise jwt.InvalidTokenError("Nonce mismatch.")

    if "azp" in claims and claims["azp"] != client_id:
        raise jwt.InvalidTokenError("Unexpected authorized party.")

    # For RS256, at_hash uses the left half of a SHA-256 digest.
    if "at_hash" in claims:
        digest = hashlib.sha256(access_token.encode("ascii")).digest()
        expected_hash = base64.urlsafe_b64encode(
            digest[: len(digest) // 2]
        ).rstrip(b"=").decode("ascii")

        actual_hash = claims["at_hash"]
        if not isinstance(actual_hash, str) or not secrets.compare_digest(
            actual_hash.encode("utf-8"),
            expected_hash.encode("ascii"),
        ):
            raise jwt.InvalidTokenError("Access token hash mismatch.")

    return claims
