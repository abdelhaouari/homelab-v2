import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from promotion_api.authentication import ISSUER
from promotion_api.main import app


class AuthenticationTests(unittest.TestCase):
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
            "iss": ISSUER,
            "aud": ["promotion-api", "account"],
            "sub": "test-user",
            "iat": now,
            "exp": now + 300,
            "typ": "Bearer",
            "resource_access": {
                "promotion-api": {"roles": ["developer"]},
                "account": {"roles": ["manage-account"]},
            },
        }

        self.key_lookup = self.enterContext(
            patch(
                "promotion_api.authentication."
                "jwks_client.get_signing_key_from_jwt",
                return_value=SimpleNamespace(
                    key=self.private_key.public_key()
                ),
            )
        )
        self.client = self.enterContext(TestClient(app))

    def call_me(self, signing_key=None):
        token = jwt.encode(
            self.claims,
            signing_key or self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )
        return self.client.get(
            "/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    def assert_unauthorized(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_valid_access_token_returns_api_roles_only(self):
        response = self.call_me()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"subject": "test-user", "roles": ["developer"]},
        )

    def test_missing_token_is_rejected(self):
        self.assert_unauthorized(self.client.get("/me"))
        self.key_lookup.assert_not_called()

    def test_wrong_signature_is_rejected(self):
        self.assert_unauthorized(self.call_me(signing_key=self.other_key))

    def test_wrong_issuer_is_rejected(self):
        self.claims["iss"] = "https://untrusted.example/realm"
        self.assert_unauthorized(self.call_me())

    def test_client_audience_is_rejected_by_api(self):
        self.claims["aud"] = "promotion-cli"
        self.assert_unauthorized(self.call_me())

    def test_expired_access_token_is_rejected(self):
        self.claims["iat"] = int(time.time()) - 600
        self.claims["exp"] = int(time.time()) - 300
        self.assert_unauthorized(self.call_me())

    def test_id_token_type_is_rejected_even_with_api_audience(self):
        self.claims["typ"] = "ID"
        self.assert_unauthorized(self.call_me())

    def test_roles_from_other_clients_grant_no_api_permissions(self):
        self.claims["resource_access"] = {
            "another-api": {"roles": ["approver"]},
        }
        response = self.call_me()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"subject": "test-user", "roles": []},
        )


if __name__ == "__main__":
    unittest.main()
