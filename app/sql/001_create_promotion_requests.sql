BEGIN;

CREATE TABLE promotion_requests (
    id UUID PRIMARY KEY,

    image_repository TEXT NOT NULL,
    image_digest TEXT NOT NULL,
    target TEXT NOT NULL,

    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    decided_by TEXT,
    decided_at TIMESTAMPTZ,

    CONSTRAINT valid_image_repository CHECK (
        length(btrim(image_repository)) > 0
        AND image_repository = btrim(image_repository)
    ),

    CONSTRAINT valid_image_digest CHECK (
        image_digest ~ '^sha256:[0-9a-f]{64}$'
    ),

    CONSTRAINT supported_target CHECK (
        target = 'staging'
    ),

    CONSTRAINT valid_requester CHECK (
        length(btrim(requested_by)) > 0
    ),

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'approved', 'rejected')
    ),

    CONSTRAINT consistent_decision CHECK (
        (
            status = 'pending'
            AND decided_by IS NULL
            AND decided_at IS NULL
        )
        OR
        (
            status IN ('approved', 'rejected')
            AND decided_by IS NOT NULL
            AND length(btrim(decided_by)) > 0
            AND decided_at IS NOT NULL
            AND decided_by <> requested_by
            AND decided_at >= created_at
        )
    )
);

CREATE INDEX promotion_requests_created_at_idx
    ON promotion_requests (created_at DESC, id);

COMMIT;
