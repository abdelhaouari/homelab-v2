"""PostgreSQL integration tests using the restricted application account."""

import unittest
from getpass import getpass
from uuid import uuid4

import psycopg

from promotion_api.domain import (
    Actor,
    AuthorizationError,
    ConflictError,
    Role,
    Status,
)
from promotion_api.repository import (
    create_request,
    get_request,
    record_decision,
)


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = getpass("PostgreSQL password for promotion_app: ")

    def setUp(self):
        self.connection = psycopg.connect(
            host="127.0.0.1",
            port=5433,
            dbname="promotion",
            user="promotion_app",
            password=self.password,
            connect_timeout=5,
            application_name="promotion-integration-tests",
        )

        # Cleanups execute in reverse order, even when a test fails.
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)

        self.developer = Actor(
            subject="test-developer",
            roles=frozenset({Role.DEVELOPER}),
        )
        self.reader = Actor(
            subject="test-reader",
            roles=frozenset({Role.READER}),
        )
        self.approver = Actor(
            subject="test-approver",
            roles=frozenset({Role.APPROVER}),
        )
        self.digest = "sha256:" + "a" * 64

    def test_create_and_read_request(self):
        created = create_request(
            self.connection,
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )

        loaded = get_request(
            self.connection,
            self.reader,
            created.id,
        )

        self.assertEqual(loaded, created)
        self.assertEqual(created.status, Status.PENDING)
        self.assertEqual(created.requested_by, self.developer.subject)
        self.assertIsNone(created.decided_by)
        self.assertIsNone(created.decided_at)

    def test_missing_request_returns_none(self):
        result = get_request(
            self.connection,
            self.reader,
            uuid4(),
        )

        self.assertIsNone(result)

    def test_reader_cannot_create_request(self):
        with self.assertRaises(AuthorizationError):
            create_request(
                self.connection,
                self.reader,
                "ghcr.io/example/application",
                self.digest,
            )

    def test_actor_without_roles_cannot_read(self):
        created = create_request(
            self.connection,
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )
        actor = Actor(
            subject="test-no-role",
            roles=frozenset(),
        )

        with self.assertRaises(AuthorizationError):
            get_request(self.connection, actor, created.id)

    def test_database_rejects_digest_update(self):
        created = create_request(
            self.connection,
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )

        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.connection.execute(
                """
                UPDATE public.promotion_requests
                SET image_digest = %s
                WHERE id = %s
                """,
                ("sha256:" + "b" * 64, created.id),
            )

    def test_approval_and_rejection_are_stored(self):
        for decision in (Status.APPROVED, Status.REJECTED):
            with self.subTest(decision=decision):
                created = create_request(
                    self.connection,
                    self.developer,
                    "ghcr.io/example/application",
                    self.digest,
                )

                decided = record_decision(
                    self.connection,
                    self.approver,
                    created.id,
                    decision,
                )
                loaded = get_request(
                    self.connection,
                    self.reader,
                    created.id,
                )

                self.assertEqual(loaded, decided)
                self.assertEqual(decided.status, decision)
                self.assertEqual(decided.decided_by, self.approver.subject)
                self.assertIsNotNone(decided.decided_at)
                self.assertEqual(decided.image_digest, created.image_digest)
                self.assertEqual(decided.requested_by, created.requested_by)

    def test_reader_cannot_record_a_decision(self):
        created = create_request(
            self.connection,
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )

        with self.assertRaises(AuthorizationError):
            record_decision(
                self.connection,
                self.reader,
                created.id,
                Status.APPROVED,
            )

        loaded = get_request(self.connection, self.reader, created.id)
        self.assertEqual(loaded, created)

    def test_self_decision_does_not_change_stored_request(self):
        created = create_request(
            self.connection,
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )
        actor = Actor(
            subject=self.developer.subject,
            roles=frozenset({Role.DEVELOPER, Role.APPROVER}),
        )

        for decision in (Status.APPROVED, Status.REJECTED):
            with self.subTest(decision=decision):
                with self.assertRaises(AuthorizationError):
                    record_decision(
                        self.connection,
                        actor,
                        created.id,
                        decision,
                    )

        loaded = get_request(self.connection, self.reader, created.id)
        self.assertEqual(loaded, created)

    def test_second_decision_preserves_the_first(self):
        for initial in (Status.APPROVED, Status.REJECTED):
            created = create_request(
                self.connection,
                self.developer,
                "ghcr.io/example/application",
                self.digest,
            )
            first = record_decision(
                self.connection,
                self.approver,
                created.id,
                initial,
            )

            for subsequent in (Status.APPROVED, Status.REJECTED):
                with self.subTest(initial=initial, subsequent=subsequent):
                    with self.assertRaises(ConflictError):
                        record_decision(
                            self.connection,
                            self.approver,
                            created.id,
                            subsequent,
                        )

            loaded = get_request(self.connection, self.reader, created.id)
            self.assertEqual(loaded, first)

    def test_decision_on_missing_request_is_rejected(self):
        with self.assertRaises(LookupError):
            record_decision(
                self.connection,
                self.approver,
                uuid4(),
                Status.APPROVED,
            )


if __name__ == "__main__":
    unittest.main()
