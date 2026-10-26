import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from promotion_api.authentication import get_current_actor
from promotion_api.domain import Actor, Role
from promotion_api.main import app


class PromotionRouteTests(unittest.TestCase):
    def setUp(self):
        self.actor = Actor(
            subject="reader-user",
            roles=frozenset({Role.READER}),
        )
        app.dependency_overrides[get_current_actor] = lambda: self.actor
        self.addCleanup(app.dependency_overrides.clear)

        self.connect_mock = self.enterContext(
            patch("promotion_api.routes.connect_database")
        )
        connection = self.connect_mock.return_value.__enter__.return_value
        self.cursor = connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = None
        self.cursor.fetchall.return_value = []

        self.client = self.enterContext(TestClient(app))
        self.request_id = uuid4()
        self.path = f"/promotion-requests/{self.request_id}"

        self.body = {
            "image_repository": "example/test-image",
            "image_digest": "sha256:" + "a" * 64,
            "target": "staging",
        }
        self.row = {
            "id": self.request_id,
            **self.body,
            "requested_by": "developer-user",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "decided_by": None,
            "decided_at": None,
        }

    def test_reader_can_read_request(self):
        self.cursor.fetchone.return_value = self.row

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.request_id))
        self.assertEqual(response.json()["requested_by"], "developer-user")

    def test_reader_can_list_requests(self):
        self.cursor.fetchall.return_value = [self.row]

        response = self.client.get("/promotion-requests")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()],
            [str(self.request_id)],
        )

    def test_actor_without_roles_cannot_read(self):
        self.actor = Actor(subject="no-role-user", roles=frozenset())

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 403)
        self.cursor.execute.assert_not_called()

    def test_reader_cannot_create_request(self):
        response = self.client.post("/promotion-requests", json=self.body)

        self.assertEqual(response.status_code, 403)
        self.cursor.execute.assert_not_called()

    def test_reader_cannot_decide_request(self):
        response = self.client.post(
            f"{self.path}/decision",
            json={"decision": "approved"},
        )

        self.assertEqual(response.status_code, 403)
        self.cursor.execute.assert_not_called()

    def test_client_cannot_supply_requester_identity(self):
        self.actor = Actor(
            subject="developer-user",
            roles=frozenset({Role.DEVELOPER}),
        )

        response = self.client.post(
            "/promotion-requests",
            json={**self.body, "requested_by": "another-user"},
        )

        self.assertEqual(response.status_code, 422)
        self.connect_mock.assert_not_called()

    def test_pending_is_not_an_http_decision(self):
        self.actor = Actor(
            subject="approver-user",
            roles=frozenset({Role.APPROVER}),
        )

        response = self.client.post(
            f"{self.path}/decision",
            json={"decision": "pending"},
        )

        self.assertEqual(response.status_code, 422)
        self.connect_mock.assert_not_called()

    def test_page_size_above_limit_is_rejected(self):
        response = self.client.get(
            "/promotion-requests",
            params={"limit": 101},
        )

        self.assertEqual(response.status_code, 422)
        self.connect_mock.assert_not_called()

    def test_missing_request_returns_not_found(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
