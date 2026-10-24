BEGIN;

CREATE ROLE promotion_app
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE promotion TO promotion_app;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO promotion_app;

GRANT SELECT
    ON TABLE public.promotion_requests
    TO promotion_app;

GRANT INSERT (
    id,
    image_repository,
    image_digest,
    target,
    requested_by,
    created_at
)
    ON TABLE public.promotion_requests
    TO promotion_app;

GRANT UPDATE (
    status,
    decided_by,
    decided_at
)
    ON TABLE public.promotion_requests
    TO promotion_app;

COMMIT;
