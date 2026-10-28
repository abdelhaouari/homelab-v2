#!/usr/bin/env bash
set -euo pipefail

# Bootstrap only: executed by the PostgreSQL image on an empty data directory.
# Existing application SQL files are mounted separately under /bootstrap/sql.

if [[ "${POSTGRES_USER:-}" != "postgres" ||
      "${POSTGRES_DB:-}" != "promotion" ]]; then
  printf 'Expected POSTGRES_USER=postgres and POSTGRES_DB=promotion.\n' >&2
  exit 1
fi

export PROMOTION_APP_PASSWORD
export KEYCLOAK_DB_PASSWORD

PROMOTION_APP_PASSWORD="$(
  cat /run/secrets/database/promotion-app-password
)"
KEYCLOAK_DB_PASSWORD="$(
  cat /run/secrets/database/keycloak-db-password
)"

trap 'unset PROMOTION_APP_PASSWORD KEYCLOAK_DB_PASSWORD' EXIT

if [[ -z "$PROMOTION_APP_PASSWORD" || -z "$KEYCLOAK_DB_PASSWORD" ]]; then
  printf 'Database role password files must not be empty.\n' >&2
  exit 1
fi

psql_bootstrap() {
  psql \
    --no-psqlrc \
    --no-password \
    --username "$POSTGRES_USER" \
    --dbname promotion \
    --set ON_ERROR_STOP=1 \
    "$@"
}

psql_bootstrap \
  --file /bootstrap/sql/001_create_promotion_requests.sql

psql_bootstrap \
  --file /bootstrap/sql/002_create_application_role.sql

psql_bootstrap <<'SQL'
\getenv promotion_password PROMOTION_APP_PASSWORD
\getenv keycloak_password KEYCLOAK_DB_PASSWORD

ALTER ROLE promotion_app PASSWORD :'promotion_password';

REVOKE ALL ON DATABASE promotion FROM PUBLIC;

CREATE ROLE keycloak
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    PASSWORD :'keycloak_password';

CREATE DATABASE keycloak OWNER keycloak;

REVOKE ALL ON DATABASE keycloak FROM PUBLIC;
GRANT CONNECT ON DATABASE keycloak TO keycloak;
SQL

printf 'Application and Keycloak database bootstrap completed.\n'
