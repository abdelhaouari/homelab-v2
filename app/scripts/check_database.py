"""Check local PostgreSQL access without storing credentials."""

from getpass import getpass

import psycopg


def main() -> None:
    password = getpass("PostgreSQL password for promotion_app: ")

    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname="promotion",
        user="promotion_app",
        password=password,
        connect_timeout=5,
        application_name="promotion-db-check",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_user,
                    current_database(),
                    count(*)
                FROM public.promotion_requests
                """)
            user, database, request_count = cursor.fetchone()

    print(f"Database user: {user}")
    print(f"Database name: {database}")
    print(f"Promotion requests: {request_count}")


if __name__ == "__main__":
    main()
