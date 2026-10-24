"""Business rules for artifact promotion requests."""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class Role(StrEnum):
    READER = "reader"
    DEVELOPER = "developer"
    APPROVER = "approver"


class Status(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AuthorizationError(Exception):
    """The actor is not allowed to perform the operation."""


class ConflictError(Exception):
    """The operation conflicts with the request's current state."""


@dataclass(frozen=True)
class Actor:
    subject: str
    roles: frozenset[Role]

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("Actor subject must not be empty.")


@dataclass(frozen=True)
class PromotionRequest:
    id: UUID
    image_repository: str
    image_digest: str
    target: str
    requested_by: str
    status: Status
    created_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None


def submit_request(
    actor: Actor,
    image_repository: str,
    image_digest: str,
    target: str = "staging",
) -> PromotionRequest:
    """Create a pending request using the authenticated actor's identity."""
    if Role.DEVELOPER not in actor.roles:
        raise AuthorizationError("The developer role is required.")

    if not image_repository or image_repository != image_repository.strip():
        raise ValueError("Image repository must be nonempty and trimmed.")

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
        raise ValueError("Expected a SHA-256 digest with 64 lowercase hex digits.")

    if target != "staging":
        raise ValueError("Only the staging environment is supported.")

    return PromotionRequest(
        id=uuid4(),
        image_repository=image_repository,
        image_digest=image_digest,
        target=target,
        requested_by=actor.subject,
        status=Status.PENDING,
        created_at=datetime.now(timezone.utc),
    )


def decide_request(
    request: PromotionRequest,
    actor: Actor,
    decision: Status,
) -> PromotionRequest:
    """Return a new request containing an authorized decision."""
    if Role.APPROVER not in actor.roles:
        raise AuthorizationError("The approver role is required.")

    if actor.subject == request.requested_by:
        raise AuthorizationError("Requesters cannot decide their own requests.")

    if decision not in (Status.APPROVED, Status.REJECTED):
        raise ValueError("A decision must approve or reject the request.")

    if request.status != Status.PENDING:
        raise ConflictError("The request already has a decision.")

    return replace(
        request,
        status=decision,
        decided_by=actor.subject,
        decided_at=datetime.now(timezone.utc),
    )
