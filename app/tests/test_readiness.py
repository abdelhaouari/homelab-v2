import unittest
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient

from promotion_api.main import app


class ReadinessEndpointTests(unittest.TestCase):
    @patch("promotion_api.main.connect_database")
    def test_ready_when_database_responds(self, connect_mock):
        connection = connect_mock.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)

        with TestClient(app) as client:
            response = client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    @patch("promotion_api.main.connect_database")
    def test_database_failure_does_not_break_liveness(self, connect_mock):
        connect_mock.side_effect = psycopg.OperationalError(
            "Internal database connection details"
        )

        with TestClient(app) as client:
            readiness = client.get("/readyz")
            health = client.get("/healthz")

        self.assertEqual(readiness.status_code, 503)
        self.assertEqual(readiness.json(), {"status": "not_ready"})
        self.assertNotIn("Internal database", readiness.text)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})

    @patch("promotion_api.main.connect_database")
    def test_not_ready_when_password_file_is_missing(self, connect_mock):
        connect_mock.side_effect = FileNotFoundError(
            "Internal secret file path"
        )

        with TestClient(app) as client:
            response = client.get("/readyz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})
        self.assertNotIn("Internal secret", response.text)


if __name__ == "__main__":
    unittest.main()
