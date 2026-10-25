import os
from pathlib import Path

import psycopg


def connect_database() -> psycopg.Connection:
    password_file = os.environ.get("PROMOTION_DB_PASSWORD_FILE")
    if not password_file:
        raise ValueError("PROMOTION_DB_PASSWORD_FILE must be configured.")

    password = Path(password_file).read_text(encoding="utf-8")
    if not password:
        raise ValueError("Database password file must not be empty.")

    return psycopg.connect(
        host=os.environ.get("PROMOTION_DB_HOST", "127.0.0.1"),
        port=os.environ.get("PROMOTION_DB_PORT", "5433"),
        dbname=os.environ.get("PROMOTION_DB_NAME", "promotion"),
        user=os.environ.get("PROMOTION_DB_USER", "promotion_app"),
        password=password,
        connect_timeout=3,
        application_name="promotion-api",
    )
