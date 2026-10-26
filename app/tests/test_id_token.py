import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from validate_id_token import validate_id_token


class IDTokenValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.other_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

    def setUp(self):
        now = int(time.time())
        self.claims = {
            "iss": "http://localhost:8080/realms/homelab",
            "sub": "test-user",
            "aud": "promotion-cli",
            "iat": now,
            "exp": now + 300,
            "nonce": "expected-test-nonce",
            "azp": "promotion-cli",
        }

    def validate(self, claims, signing_key=None):
        encoded = jwt.encode(
            claims,
            signing_key or self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        with patch("validate_id_token.PyJWKClient") as jwks_mock:
            jwks_mock.return_value.get_signing_key_from_jwt.return_value = (
                SimpleNamespace(key=self.private_key.public_key())
            )

            return validate_id_token(
                encoded,
                issuer="http://localhost:8080/realms/homelab",
                client_id="promotion-cli",
                expected_nonce="expected-test-nonce",
                access_token="test-access-token",
            )

    def test_valid_id_token_is_accepted(self):
        identity = self.validate(self.claims)
        self.assertEqual(identity["sub"], "test-user")

    def test_wrong_signature_is_rejected(self):
        with self.assertRaises(jwt.InvalidSignatureError):
            self.validate(self.claims, signing_key=self.other_key)

    def test_wrong_issuer_is_rejected(self):
        self.claims["iss"] = "https://untrusted.example/realm"
        with self.assertRaises(jwt.InvalidIssuerError):
            self.validate(self.claims)

    def test_api_audience_is_rejected_for_id_token(self):
        self.claims["aud"] = "promotion-api"
        with self.assertRaises(jwt.InvalidAudienceError):
            self.validate(self.claims)

    def test_expired_token_is_rejected(self):
        self.claims["iat"] = int(time.time()) - 600
        self.claims["exp"] = int(time.time()) - 300
        with self.assertRaises(jwt.ExpiredSignatureError):
            self.validate(self.claims)

    def test_wrong_nonce_is_rejected(self):
        self.claims["nonce"] = "another-login-attempt"
        with self.assertRaisesRegex(jwt.InvalidTokenError, "Nonce mismatch"):
            self.validate(self.claims)

    def test_missing_nonce_is_rejected(self):
        del self.claims["nonce"]
        with self.assertRaises(jwt.MissingRequiredClaimError):
            self.validate(self.claims)


if __name__ == "__main__":
    unittest.main()
