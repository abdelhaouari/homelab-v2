BEGIN;

DO $$
DECLARE
    request_id UUID := gen_random_uuid();
    rejected_constraint TEXT;
BEGIN
    -- A valid pending request must be accepted.
    INSERT INTO promotion_requests (
        id,
        image_repository,
        image_digest,
        target,
        requested_by
    )
    VALUES (
        request_id,
        'ghcr.io/example/application',
        'sha256:' || repeat('a', 64),
        'staging',
        'developer-1'
    );

    RAISE NOTICE 'PASS: valid pending request accepted';

    -- A malformed digest must be rejected.
    BEGIN
        UPDATE promotion_requests
        SET image_digest = 'invalid-digest'
        WHERE id = request_id;

        RAISE EXCEPTION 'FAIL: invalid digest was accepted';
    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS
                rejected_constraint = CONSTRAINT_NAME;

            IF rejected_constraint <> 'valid_image_digest' THEN
                RAISE;
            END IF;

            RAISE NOTICE 'PASS: invalid digest rejected';
    END;

    -- An approval without decision metadata must be rejected.
    BEGIN
        UPDATE promotion_requests
        SET status = 'approved'
        WHERE id = request_id;

        RAISE EXCEPTION 'FAIL: incomplete decision was accepted';
    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS
                rejected_constraint = CONSTRAINT_NAME;

            IF rejected_constraint <> 'consistent_decision' THEN
                RAISE;
            END IF;

            RAISE NOTICE 'PASS: incomplete decision rejected';
    END;

    -- The requester must not approve their own request.
    BEGIN
        UPDATE promotion_requests
        SET status = 'approved',
            decided_by = 'developer-1',
            decided_at = CURRENT_TIMESTAMP
        WHERE id = request_id;

        RAISE EXCEPTION 'FAIL: self-approval was accepted';
    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS
                rejected_constraint = CONSTRAINT_NAME;

            IF rejected_constraint <> 'consistent_decision' THEN
                RAISE;
            END IF;

            RAISE NOTICE 'PASS: self-approval rejected';
    END;

    -- A complete decision from another identity must be accepted.
    UPDATE promotion_requests
    SET status = 'approved',
        decided_by = 'approver-1',
        decided_at = CURRENT_TIMESTAMP
    WHERE id = request_id;

    RAISE NOTICE 'PASS: complete decision accepted';
END;
$$;

ROLLBACK;
