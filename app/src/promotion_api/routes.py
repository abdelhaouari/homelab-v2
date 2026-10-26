from typing import Annotated
from uuid import UUID
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel, ConfigDict, Field

from promotion_api.authentication import get_current_actor
from promotion_api.database import connect_database
from promotion_api.domain import (
    Actor,
    AuthorizationError,
    PromotionRequest,
    ConflictError,
    Status,
)
from promotion_api.repository import (
    create_request,
    get_request,
    record_decision,
    list_requests,
)

router = APIRouter(
    prefix="/promotion-requests",
    tags=["promotion requests"],
)

CurrentActor = Annotated[Actor, Depends(get_current_actor)]


class CreatePromotionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    image_repository: str = Field(min_length=1, max_length=255)
    image_digest: str = Field(min_length=71, max_length=71)
    target: str = Field(default="staging", max_length=32)


@router.post("", status_code=201, response_model=PromotionRequest)
def submit_promotion(
    body: CreatePromotionBody,
    actor: CurrentActor,
    response: Response,
) -> PromotionRequest:
    try:
        with connect_database() as connection:
            try:
                request = create_request(
                    connection=connection,
                    actor=actor,
                    image_repository=body.image_repository,
                    image_digest=body.image_digest,
                    target=body.target,
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from None
    except AuthorizationError:
        raise HTTPException(
            status_code=403,
            detail="The developer role is required.",
        ) from None
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable.",
        ) from None

    response.headers["Location"] = f"/promotion-requests/{request.id}"
    return request


@router.get("/{request_id}", response_model=PromotionRequest)
def read_promotion(
    request_id: UUID,
    actor: CurrentActor,
) -> PromotionRequest:
    try:
        with connect_database() as connection:
            request = get_request(
                connection=connection,
                actor=actor,
                request_id=request_id,
            )
    except AuthorizationError:
        raise HTTPException(
            status_code=403,
            detail="A role with read access is required.",
        ) from None
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable.",
        ) from None

    if request is None:
        raise HTTPException(
            status_code=404,
            detail="Promotion request not found.",
        )

    return request


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["approved", "rejected"]


@router.post("/{request_id}/decision", response_model=PromotionRequest)
def decide_promotion(
    request_id: UUID,
    body: DecisionBody,
    actor: CurrentActor,
) -> PromotionRequest:
    try:
        with connect_database() as connection:
            request = record_decision(
                connection=connection,
                actor=actor,
                request_id=request_id,
                decision=Status(body.decision),
            )
    except AuthorizationError:
        raise HTTPException(
            status_code=403,
            detail="This actor cannot decide this request.",
        ) from None
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Promotion request not found.",
        ) from None
    except ConflictError:
        raise HTTPException(
            status_code=409,
            detail="The request already has a decision.",
        ) from None
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable.",
        ) from None

    return request


@router.get("", response_model=list[PromotionRequest])
def list_promotions(
    actor: CurrentActor,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PromotionRequest]:
    try:
        with connect_database() as connection:
            requests = list_requests(
                connection=connection,
                actor=actor,
                limit=limit,
                offset=offset,
            )
    except AuthorizationError:
        raise HTTPException(
            status_code=403,
            detail="A role with read access is required.",
        ) from None
    except psycopg.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable.",
        ) from None

    return requests
