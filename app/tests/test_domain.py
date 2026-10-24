"""Tests for promotion authorization and state transitions."""

import unittest
from dataclasses import FrozenInstanceError

from promotion_api.domain import (
    Actor,
    AuthorizationError,
    ConflictError,
    Role,
    Status,
    decide_request,
    submit_request,
)


class PromotionRulesTests(unittest.TestCase):
    def setUp(self):
        self.developer = Actor(
            subject="developer-1",
            roles=frozenset({Role.DEVELOPER}),
        )
        self.approver = Actor(
            subject="approver-1",
            roles=frozenset({Role.APPROVER}),
        )
        self.reader = Actor(
            subject="reader-1",
            roles=frozenset({Role.READER}),
        )
        self.digest = "sha256:" + "a" * 64
        self.request = submit_request(
            self.developer,
            "ghcr.io/example/application",
            self.digest,
        )

    def test_submission_records_actor_and_pending_state(self):
        self.assertEqual(self.request.requested_by, self.developer.subject)
        self.assertEqual(self.request.status, Status.PENDING)
        self.assertEqual(self.request.target, "staging")
        self.assertIsNone(self.request.decided_by)
        self.assertIsNone(self.request.decided_at)
        self.assertIsNotNone(self.request.created_at.utcoffset())

    def test_reader_cannot_submit(self):
        with self.assertRaises(AuthorizationError):
            submit_request(self.reader, "example/application", self.digest)

    def test_only_approver_can_decide(self):
        for actor in (self.reader, self.developer):
            with self.subTest(actor=actor.subject):
                with self.assertRaises(AuthorizationError):
                    decide_request(self.request, actor, Status.APPROVED)

    def test_self_decision_is_denied_even_with_both_roles(self):
        actor = Actor(
            subject=self.developer.subject,
            roles=frozenset({Role.DEVELOPER, Role.APPROVER}),
        )
        for decision in (Status.APPROVED, Status.REJECTED):
            with self.subTest(decision=decision):
                with self.assertRaises(AuthorizationError):
                    decide_request(self.request, actor, decision)

    def test_approver_can_approve_or_reject(self):
        for decision in (Status.APPROVED, Status.REJECTED):
            with self.subTest(decision=decision):
                result = decide_request(self.request, self.approver, decision)

                self.assertEqual(result.status, decision)
                self.assertEqual(result.decided_by, self.approver.subject)
                self.assertIsNotNone(result.decided_at)
                self.assertEqual(result.id, self.request.id)
                self.assertEqual(result.image_repository, self.request.image_repository)
                self.assertEqual(result.image_digest, self.request.image_digest)
                self.assertEqual(result.target, self.request.target)
                self.assertEqual(result.requested_by, self.request.requested_by)
                self.assertEqual(result.created_at, self.request.created_at)
                self.assertEqual(self.request.status, Status.PENDING)

    def test_decided_request_cannot_receive_another_decision(self):
        for initial in (Status.APPROVED, Status.REJECTED):
            decided = decide_request(self.request, self.approver, initial)
            for subsequent in (Status.APPROVED, Status.REJECTED):
                with self.subTest(initial=initial, subsequent=subsequent):
                    with self.assertRaises(ConflictError):
                        decide_request(decided, self.approver, subsequent)

    def test_pending_is_not_a_decision(self):
        with self.assertRaises(ValueError):
            decide_request(self.request, self.approver, Status.PENDING)

    def test_invalid_digests_are_rejected(self):
        invalid_digests = [
            "",
            "latest",
            "sha256:" + "a" * 63,
            "sha256:" + "a" * 65,
            "sha256:" + "g" * 64,
            "sha256:" + "A" * 64,
        ]
        for digest in invalid_digests:
            with self.subTest(digest=digest):
                with self.assertRaises(ValueError):
                    submit_request(self.developer, "example/application", digest)

    def test_only_staging_is_supported(self):
        with self.assertRaises(ValueError):
            submit_request(
                self.developer,
                "example/application",
                self.digest,
                target="production",
            )

    def test_digest_cannot_be_assigned_after_submission(self):
        with self.assertRaises(FrozenInstanceError):
            self.request.image_digest = "sha256:" + "b" * 64


if __name__ == "__main__":
    unittest.main()
