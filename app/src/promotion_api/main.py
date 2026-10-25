import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from promotion_api.database import connect_database

app = FastAPI(
    title="Promotion API",
    version="0.1.0",
    description="Image promotion requests and approval decisions.",
)


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
