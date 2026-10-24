"""Verify that competing decisions cannot overwrite each other."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import psycopg

from promotion_api import repository
from promotion_api.domain import Actor, ConflictError, Role, Status


class ConcurrentDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_password = getpass("PostgreSQL password for promotion_app: ")
        project_root = Path(__file__).resolve().parents[2]
        cls.admin_password = (
            (project_root / "private" / "postgres-password.txt").read_text().strip()
        )

    def connect(self, admin=False):
        connection = psycopg.connect(
            host="127.0.0.1",
            port=5433,
            dbname="promotion",
            user="postgres" if admin else "promotion_app",
            password=self.admin_password if admin else self.app_password,
            connect_timeout=5,
            options="-c statement_timeout=15000 -c lock_timeout=10000",
            application_name="promotion-concurrency-test",
        )
        connection.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
        return connection

    def delete_test_request(self, request_id):
        with self.connect(admin=True) as connection:
            connection.execute(
                "DELETE FROM public.promotion_requests WHERE id = %s",
                (request_id,),
            )

    def test_only_one_concurrent_decision_is_committed(self):
        # Verify cleanup access before creating committed test data.
        with self.connect(admin=True) as connection:
            connection.execute("SELECT 1")

        developer = Actor(
            subject="concurrency-developer",
            roles=frozenset({Role.DEVELOPER}),
        )

        with self.connect() as connection:
            created = repository.create_request(
                connection,
                developer,
                "ghcr.io/example/concurrency-test",
                "sha256:" + "c" * 64,
            )
            self.addCleanup(self.delete_test_request, created.id)
        # Exiting the connection context commits the new request.

        barrier = Barrier(2)
        original_get_request = repository.get_request

        def synchronized_read(connection, actor, request_id):
            result = original_get_request(connection, actor, request_id)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, Status.PENDING)
            barrier.wait(timeout=10)
            return result

        def attempt_decision(subject, decision):
            actor = Actor(
                subject=subject,
                roles=frozenset({Role.APPROVER}),
            )
            try:
                with self.connect() as connection:
                    result = repository.record_decision(
                        connection,
                        actor,
                        created.id,
                        decision,
                    )
                # Return success only after the commit succeeds.
                return ("committed", result)
            except ConflictError:
                return ("conflict", None)

        # Synchronize the reads; all SQL still runs against PostgreSQL.
        with patch.object(
            repository,
            "get_request",
            side_effect=synchronized_read,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        attempt_decision,
                        "concurrency-approver-a",
                        Status.APPROVED,
                    ),
                    executor.submit(
                        attempt_decision,
                        "concurrency-approver-b",
                        Status.REJECTED,
                    ),
                ]
                results = [future.result(timeout=30) for future in futures]

        self.assertCountEqual(
            [outcome for outcome, _ in results],
            ["committed", "conflict"],
        )

        winner = next(result for outcome, result in results if outcome == "committed")

        # A separate connection must see the committed winning decision.
        with self.connect() as connection:
            stored = repository.get_request(
                connection,
                developer,
                created.id,
            )

        self.assertEqual(stored, winner)
        self.assertEqual(stored.image_digest, created.image_digest)


if __name__ == "__main__":
    unittest.main()
