# Artifact promotion API

## Status

The Python domain layer, PostgreSQL persistence, and HTTP health
endpoints are implemented and tested locally.

Completed:

- Promotion submission and approval/rejection rules.
- Role checks and prevention of self-approval or self-rejection.
- PostgreSQL schema with data consistency constraints.
- A restricted application database account.
- Parameterized queries for creation, retrieval, and decisions.
- Conditional updates preventing concurrent decisions from overwriting
  each other.
- FastAPI health endpoints served locally with Uvicorn.
- Database connection configuration through environment variables,
  with the application password read from a local file excluded from Git.

Observed validation:

- 10 domain unit tests passed.
- 10 PostgreSQL integration tests passed.
- 1 concurrent-decision test passed using two database connections.
- 5 SQL checks passed for valid requests and decision consistency.
- 1 HTTP liveness test and 3 HTTP readiness tests passed in separate runs.
- Stopping PostgreSQL caused readiness to return HTTP 503 while liveness
  continued to return HTTP 200.
- Restarting PostgreSQL restored HTTP 200 readiness without restarting
  the application.

The concurrency test forced both transactions to read a pending request.
One decision committed, the other raised a conflict, and a separate
connection retrieved the winning decision.

HTTP readiness tests simulate database outcomes. The PostgreSQL outage
and recovery scenario was also verified manually with Docker Compose.

Business HTTP endpoints, OIDC authentication, the application container,
and the CI/CD pipeline are not implemented yet. Business-rule tests use
synthetic identities.

FastAPI currently runs directly in WSL. PostgreSQL runs in a local
Docker container managed by Docker Compose. Neither component is
deployed to the homelab Kubernetes cluster yet.

## Purpose

Build a small Python API to practice application security and secure
delivery on the homelab Kubernetes platform.

The API records requests to promote a container image to a target
environment. It records approval decisions but does not deploy images.

## Initial scope

- Python API.
- PostgreSQL persistence.
- Automated tests for business rules and authorization.
- Container image deployed to the existing Kubernetes cluster.
- CI security checks introduced progressively.

The initial implementation supports one project and one target
environment, staging. Multi-project authorization is outside this first
iteration.

## Promotion request

Each request contains:

- A server-generated identifier.
- An image repository.
- A SHA-256 image digest.
- A target environment.
- The requesting user's identity.
- A status: pending, approved, or rejected.
- Creation and decision timestamps.
- The decision-maker's identity, when applicable.

The requester and decision-maker identities must come from the
authentication context, not client-supplied identity fields.

An image digest identifies content. It does not prove that the image is
safe, signed, or produced by a trusted build.

## Roles

| Role      | Permissions                                           |
| --------- | ----------------------------------------------------- |
| Reader    | List and inspect requests                             |
| Developer | Read requests and submit a new request                |
| Approver  | Read requests and approve or reject a pending request |

A user may hold multiple roles. The prohibition on approving one's own
request applies regardless of role combinations.

## Security invariants

These are target security requirements. Domain and database tests cover
the implemented business rules; HTTP authentication and authorization
remain to be implemented and validated.

1. Unauthenticated requests cannot access application records.
2. Read-only users cannot create requests or make decisions.
3. A requester cannot approve or reject their own request.
4. The image repository, digest, and target cannot change after submission.
5. A decision can only transition a request from pending to approved
   or rejected.
6. Concurrent decisions cannot overwrite each other.
7. Identity and decision timestamps are assigned by the server.
8. Invalid input is rejected before persistence.
9. Credentials and access tokens must not appear in application logs.

## HTTP endpoints

| Method | Path | Purpose | Status |
| ------ | ---- | ------- | ------ |
| GET | /healthz | Application liveness | Implemented |
| GET | /readyz | PostgreSQL connectivity and query execution | Implemented |
| POST | /promotion-requests | Submit a request | Planned |
| GET | /promotion-requests | List requests | Planned |
| GET | /promotion-requests/{id} | Inspect a request | Planned |
| POST | /promotion-requests/{id}/decision | Approve or reject a request | Planned |

Health endpoints return minimal status information without credentials
or internal error details.

Readiness establishes a database connection and executes SELECT 1.
It does not validate the application schema or exercise business
operations. Connection establishment has a three-second timeout;
SQL statements in the readiness transaction have a two-second timeout.

## Local HTTP development

Run these commands from the repository root after creating the
application virtual environment:

```bash
app/.venv/bin/python -m pip install -r app/requirements-dev.txt
docker compose -f app/compose.yml up -d --wait postgres
```

The database schema and promotion_app role must already be initialized.
Store the existing application-role password in
private/promotion-app-password.txt with permissions 0600.
The private directory is excluded from Git. This file is plaintext,
not an encrypted secret store.

Start the API:

```bash
PROMOTION_DB_PASSWORD_FILE="$PWD/private/promotion-app-password.txt" \
app/.venv/bin/python -m uvicorn promotion_api.main:app \
  --app-dir app/src \
  --host 127.0.0.1 \
  --port 8000
```

Default database settings are 127.0.0.1:5433, database promotion,
and user promotion_app. Override them with PROMOTION_DB_HOST,
PROMOTION_DB_PORT, PROMOTION_DB_NAME, and PROMOTION_DB_USER.

Run the HTTP tests without starting Uvicorn or PostgreSQL:

```bash
PYTHONPATH=app/src app/.venv/bin/python -m unittest discover \
  -s app/tests -p 'test_health.py' -v

PYTHONPATH=app/src app/.venv/bin/python -m unittest discover \
  -s app/tests -p 'test_readiness.py' -v
```

## Implementation sequence

1. Implement domain rules and unit tests.
2. Add PostgreSQL persistence and concurrency tests.
3. Add the HTTP API and authorization tests.
4. Integrate OIDC authentication before exposing business endpoints
   in the shared lab.
5. Containerize and deploy the application.
6. Add CI security checks and demonstrate failure, remediation,
   and successful delivery.

Unit tests may use synthetic identities. They must not introduce a
production authentication bypass.

## Later extensions

- Record and verify build provenance, signatures, and SBOM references.
- Use pipeline identities to submit promotion requests.
- Introduce GitOps deployment after approval.
- Validate workload isolation, secret rotation, and recovery.

These extensions are planned and are not implemented capabilities.
