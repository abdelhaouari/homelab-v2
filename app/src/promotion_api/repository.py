"""PostgreSQL persistence for promotion requests."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from promotion_api.domain import (
    Actor,
    AuthorizationError,
    ConflictError,
    PromotionRequest,
    Role,
    Status,
    decide_request,
    submit_request,
)


def _to_request(row: dict) -> PromotionRequest:
    """Convert a database row into a domain object."""
    return PromotionRequest(
        id=row["id"],
        image_repository=row["image_repository"],
        image_digest=row["image_digest"],
        target=row["target"],
        requested_by=row["requested_by"],
        status=Status(row["status"]),
        created_at=row["created_at"],
        decided_by=row["decided_by"],
        decided_at=row["decided_at"],
    )


def create_request(
    connection: psycopg.Connection,
    actor: Actor,
    image_repository: str,
    image_digest: str,
    target: str = "staging",
) -> PromotionRequest:
    """Validate and insert a request within the caller's transaction."""
    request = submit_request(
        actor,
        image_repository,
        image_digest,
        target,
    )

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            INSERT INTO public.promotion_requests (
                id,
                image_repository,
                image_digest,
                target,
                requested_by,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING
                id, image_repository, image_digest, target,
                requested_by, status, created_at,
                decided_by, decided_at
            """,
            (
                request.id,
                request.image_repository,
                request.image_digest,
                request.target,
                request.requested_by,
                request.created_at,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("The inserted request was not returned.")

    return _to_request(row)


def get_request(
    connection: psycopg.Connection,
    actor: Actor,
    request_id: UUID,
) -> PromotionRequest | None:
    """Read a request after checking the actor's read permissions."""
    allowed_roles = {Role.READER, Role.DEVELOPER, Role.APPROVER}

    if not actor.roles.intersection(allowed_roles):
        raise AuthorizationError("A role with read access is required.")

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                id, image_repository, image_digest, target,
                requested_by, status, created_at,
                decided_by, decided_at
            FROM public.promotion_requests
            WHERE id = %s
            """,
            (request_id,),
        )
        row = cursor.fetchone()

    return None if row is None else _to_request(row)


def record_decision(
    connection: psycopg.Connection,
    actor: Actor,
    request_id: UUID,
    decision: Status,
) -> PromotionRequest:
    """Record a decision only while the stored request is pending."""
    if Role.APPROVER not in actor.roles:
        raise AuthorizationError("The approver role is required.")

    current = get_request(connection, actor, request_id)

    if current is None:
        raise LookupError("Promotion request not found.")

    decided = decide_request(current, actor, decision)

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            UPDATE public.promotion_requests
            SET status = %s,
                decided_by = %s,
                decided_at = %s
            WHERE id = %s
              AND status = 'pending'
            RETURNING
                id, image_repository, image_digest, target,
                requested_by, status, created_at,
                decided_by, decided_at
            """,
            (
                decided.status.value,
                decided.decided_by,
                decided.decided_at,
                request_id,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        raise ConflictError("The request changed before the decision was saved.")

    return _to_request(row)
