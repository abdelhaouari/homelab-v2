import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from typing import Annotated

from fastapi import Depends

from promotion_api.authentication import get_current_actor
from promotion_api.domain import Actor
from promotion_api.routes import router as promotion_router

from promotion_api.database import connect_database

app = FastAPI(
    title="Promotion API",
    version="0.1.0",
    description="Image promotion requests and approval decisions.",
)

app.include_router(promotion_router)


@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz() -> JSONResponse:
    try:
        with connect_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '2s'")
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
    except (psycopg.Error, OSError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )

    if result != (1,):
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready"},
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ready"},
    )


@app.get("/me", tags=["identity"])
def read_current_identity(
    actor: Annotated[Actor, Depends(get_current_actor)],
) -> dict:
    return {
        "subject": actor.subject,
        "roles": sorted(role.value for role in actor.roles),
    }
