# Artifact promotion API

## Status

The API implements promotion submission, retrieval, listing, and
approval or rejection, with PostgreSQL persistence and Keycloak
authentication.

Implemented capabilities:

- Authorization Code flow with PKCE S256 for the local CLI.
- ID token signature, issuer, audience, expiry, and nonce validation.
- API access token validation and client-role extraction.
- Reader, developer, and approver permissions.
- Authenticated requester and decision-maker identities.
- Prevention of self-approval and self-rejection.
- PostgreSQL constraints and a restricted application database account.
- Parameterized queries and conditional updates preventing concurrent
  decisions from overwriting each other.
- Liveness and database readiness endpoints.
- A versioned Keycloak realm configuration for fresh installations.

Automated validation completed in separate runs:

| Test suite | Passed | Scope |
| ---------- | -----: | ----- |
| Domain | 10 | Business rules |
| PostgreSQL repository | 10 | Persistence and permissions |
| Concurrent decisions | 1 | Two competing database transactions |
| SQL checks | 5 | Schema constraints |
| Liveness | 1 | HTTP response |
| Readiness | 3 | Simulated database outcomes |
| ID token validation | 7 | Signed tokens with controlled keys and claims |
| API authentication | 8 | Access token validation through HTTP |
| HTTP routes | 9 | Authorization and input validation with mocked database access |

Manual end-to-end validation:

- A developer authenticated through Keycloak, submitted a request,
  and retrieved the persisted record.
- A different user with the approver role approved that request.
- Repeating the decision returned HTTP 409.
- A reader received HTTP 403 when attempting a decision, but could
  retrieve and list requests.
- Keycloak rejected an incorrect PKCE verifier with invalid_grant.
- Stopping PostgreSQL caused readiness to return HTTP 503 while
  liveness remained HTTP 200. Restarting PostgreSQL restored readiness.
- A disposable Keycloak instance imported the versioned realm and
  served its OIDC discovery document.

FastAPI runs directly in WSL. PostgreSQL and Keycloak run in local
Docker Compose containers. The application is not yet containerized
or deployed to Kubernetes. CI/CD and image signing remain planned.

The API records promotion decisions. It does not deploy images or
verify their existence, signatures, provenance, or scan results.

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

The implementation enforces the following rules through authentication,
application logic, database permissions, and constraints. The validation
above covers specific scenarios; it is not an exhaustive security audit.

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

| Method | Path | Purpose | Access |
| ------ | ---- | ------- | ------ |
| GET | /healthz | Application liveness | Public |
| GET | /readyz | Database connectivity and query execution | Public |
| GET | /me | Verified identity and application roles | Authenticated |
| POST | /promotion-requests | Submit a request | Developer |
| GET | /promotion-requests | List requests with bounded pagination | Reader, developer, approver |
| GET | /promotion-requests/{id} | Inspect a request | Reader, developer, approver |
| POST | /promotion-requests/{id}/decision | Approve or reject a pending request | Approver, excluding the requester |

Health endpoints return minimal status information without credentials
or internal error details.

Readiness establishes a database connection and executes SELECT 1.
It does not validate the application schema or exercise business
operations. Connection establishment has a three-second timeout;
SQL statements in the readiness transaction have a two-second timeout.

## Local identity configuration

Keycloak serves the homelab realm at
http://localhost:8080/realms/homelab.

The promotion-cli public client uses Authorization Code with PKCE S256
and the exact redirect URI http://127.0.0.1:8765/callback.
It has no client secret.

The promotion-api client defines the reader, developer, and approver
roles. An audience mapper includes promotion-api in access tokens
issued to the CLI.

The CLI validates ID tokens for promotion-cli. The API validates access
tokens for promotion-api and derives the actor from the verified subject
and application roles. Usernames are not used as authorization identities.

Compose mounts app/keycloak read-only into Keycloak's import directory.
The --import-realm startup option imports missing realms and skips
existing ones. Editing the JSON does not update an existing realm.

The versioned realm contains client configuration and role definitions,
but no users, passwords, or signing keys. Users and role assignments must
be provisioned separately. Recreating users generates new subjects and
does not restore identities referenced by existing promotion records.

Keycloak uses development mode and local HTTP. This configuration is
for local learning, not production deployment. Local credential files
are excluded from Git but remain plaintext. Database volumes and identity
data require a separate backup and recovery procedure.

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

## Delivery milestones

Completed locally:

1. Domain rules and PostgreSQL persistence.
2. Concurrency protection and database permission checks.
3. HTTP endpoints and role-based authorization.
4. Keycloak integration and token validation.
5. Fresh realm import validation.

Next:

1. Build and run the API container image.
2. Automate tests and security checks in CI.
3. Publish the image and introduce signing and verification.
4. Deploy the application to Kubernetes.

Automated tests use controlled identities and mocked dependencies where
appropriate. These test mechanisms do not provide an authentication
bypass in the running application.

## Later extensions

- Record and verify build provenance, signatures, and SBOM references.
- Use pipeline identities to submit promotion requests.
- Introduce GitOps deployment after approval.
- Validate workload isolation, secret rotation, and recovery.

These extensions are planned and are not implemented capabilities.
