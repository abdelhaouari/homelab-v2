import unittest

from fastapi.testclient import TestClient

from promotion_api.main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self):
        with TestClient(app) as client:
            response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/json",
        )
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
