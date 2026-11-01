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
- Browser frontend with Keycloak login, paginated requests, request
  details, developer submission, and approver decisions.

Automated validation completed in separate runs:

| Test suite            | Passed | Scope                                                          |
| --------------------- | -----: | -------------------------------------------------------------- |
| Domain                |     10 | Business rules                                                 |
| PostgreSQL repository |     10 | Persistence and permissions                                    |
| Concurrent decisions  |      1 | Two competing database transactions                            |
| SQL checks            |      5 | Schema constraints                                             |
| Liveness              |      1 | HTTP response                                                  |
| Readiness             |      3 | Simulated database outcomes                                    |
| ID token validation   |      7 | Signed tokens with controlled keys and claims                  |
| API authentication    |      8 | Access token validation through HTTP                           |
| HTTP routes           |      9 | Authorization and input validation with mocked database access |

The six service-independent suites used by CI were rerun on October 31,
2026: all 38 tests passed. Repository, concurrent-transaction, and SQL
checks in the table refer to earlier database-backed runs.

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

The API and compiled frontend are deployed to Kubernetes alongside
Keycloak and PostgreSQL, managed through Argo CD. On October 31, 2026,
the two Deployments and PostgreSQL StatefulSet were each ready at one
replica. The browser workflow, including creation, approval, rejection,
and reader inspection, was exercised in the cluster as recorded in the
[GitOps guide](../gitops/README.md).

GitHub Actions runs automated tests and security checks, builds and scans
the application image, and publishes and signs it on pushes to `main`.
Kyverno verifies application image signatures at admission in `promotion`.
See [secure delivery](delivery.md) and [container security](container-security.md).

Docker Compose and direct WSL execution remain local development paths.
The environment-specific instructions below describe those paths;
Kubernetes access and Secret names are documented in the GitOps guide.

The API records promotion decisions. It does not deploy images or
verify their existence, signatures, provenance, or scan results.

## Purpose

Build a small Python API to practice application security and secure
delivery on the homelab Kubernetes platform.

The API records requests to promote a container image to a target
environment. It records approval decisions but does not deploy images.

## Implemented scope

- Python API.
- PostgreSQL persistence.
- Automated tests for business rules and authorization.
- Container image deployed to the existing Kubernetes cluster.
- CI tests, security gates, GHCR publication, and keyless image signing.
- Argo CD deployment and Kyverno image admission.

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

| Method | Path                              | Purpose                                   | Access                            |
| ------ | --------------------------------- | ----------------------------------------- | --------------------------------- |
| GET    | /healthz                          | Application liveness                      | Public                            |
| GET    | /readyz                           | Database connectivity and query execution | Public                            |
| GET    | /me                               | Verified identity and application roles   | Authenticated                     |
| POST   | /promotion-requests               | Submit a request                          | Developer                         |
| GET    | /promotion-requests               | List requests with bounded pagination     | Reader, developer, approver       |
| GET    | /promotion-requests/{id}          | Inspect a request                         | Reader, developer, approver       |
| POST   | /promotion-requests/{id}/decision | Approve or reject a pending request       | Approver, excluding the requester |

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
roles. Audience mappers include promotion-api in access tokens
issued to the CLI and browser clients.

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

## Local browser frontend

The frontend uses JavaScript, Vite, and the official keycloak-js adapter.
It reuses the existing API endpoints and business rules.

The promotion-web public client uses Authorization Code with PKCE S256.
Its login and post-logout redirect URIs are http://localhost:5173/
and http://localhost:8000/. Its allowed web origins are
http://localhost:5173 and http://localhost:8000.

Access and refresh tokens remain in adapter memory. API requests send
the access token in the Authorization header. The interface obtains
the current subject and roles from /me. API authorization remains
mandatory regardless of which controls are visible in the browser.

Start PostgreSQL, Keycloak, and the API using the existing local
configuration. In a separate terminal, from the repository root:

```bash
cd app/frontend
npm ci
npm run dev
```

Open http://localhost:5173/. Vite uses a fixed port and proxies /me
and /promotion-requests to the API at http://127.0.0.1:8000.

To compile the frontend:

```bash
npm run build
```

The generated dist directory and node_modules are excluded from Git.
package-lock.json is versioned.

FastAPI serves the compiled frontend at / and its assets at /assets.
The browser uses its current origin for login and logout redirects.
The browser client allows both localhost:5173 for Vite development
and localhost:8000 for the application container.

Browser checks completed:

- Developer login, API-verified identity, and logout.
- Request listing and detail access for developer and reader roles.
- Creation of two requests by the developer.
- Approval of one request and rejection of another by a different user.
- Reader access to both persisted decisions without write controls.

The frontend build completed successfully. Browser checks were manual;
there is no automated browser test suite. Error messages are implemented,
but browser coverage of all error paths and pagination is not yet proven.

The promotion-web client was configured in the local running realm and
added to the versioned JSON. The local disposable-realm import test
predates that addition. The later Kubernetes deployment mounts the
versioned realm as a generated ConfigMap, and its browser login and
role-based workflow were validated. A complete fresh-cluster reproduction
has not yet been performed.

## Local container execution

The multi-stage Dockerfile builds the frontend with Node and copies
the compiled assets into the Python runtime image. Node and frontend
build dependencies are not included in the runtime image.

The application runs as UID/GID 10001:10001. Application files remain
root-owned and readable by the runtime user. Compose configures a
read-only root filesystem, drops all Linux capabilities, and enables
no-new-privileges.

The application connects to PostgreSQL at postgres:5432.
PROMOTION_OIDC_ISSUER remains http://localhost:8080/realms/homelab,
matching the issuer used by the browser. PROMOTION_OIDC_JWKS_URL
uses the internal Keycloak service address to retrieve public keys.
Signature, issuer, audience, and role validation remain enforced.

The database password is mounted at /run/secrets/promotion_app_password.
It is not included in the image. For the validated local Docker setup,
the source file grants read access to UID 10001 through a filesystem ACL:

```bash
setfacl -m u:10001:r-- private/promotion-app-password.txt
```

The acl package provides setfacl. Replacing the password file may require
reapplying this ACL. Compose file-backed secrets remain local plaintext
files; this setup does not provide an encrypted secret store.

With the existing database, users, and Keycloak configuration prepared,
run from the repository root:

```bash
docker compose -f app/compose.yml config --quiet
docker compose -f app/compose.yml up -d --build app
```

Stop any standalone Uvicorn process using port 8000 first.
Open http://localhost:8000/.

Validated in the containerized setup:

- Liveness returned HTTP 200.
- Database readiness returned HTTP 200.
- /me without a token returned HTTP 401.
- Browser login, API-verified developer identity, request listing,
  detail access, and logout worked.

Creation and approval/rejection were validated before containerization;
those write scenarios have not yet been repeated in the container.

Uvicorn access logging is disabled to avoid recording OIDC callback
URLs that may contain authorization codes. Startup and error logs remain
available. Compose waits for PostgreSQL health, but Keycloak being started
does not guarantee authentication readiness.

Base image tags and transitive Python dependencies are not fully locked
by digest or hashes. The CI-built application image is now scanned,
published to GHCR, and signed by digest. The Kubernetes Deployment pins
the selected published digest; Compose continues to build a local image.

## Kubernetes execution

Argo CD deploys the application manifests from
[`gitops/manifests/promotion/`](../gitops/manifests/promotion/).
The API/frontend and Keycloak use single-replica Deployments; PostgreSQL
uses a StatefulSet with a retained, node-local PVC.

Keycloak uses `start` with PostgreSQL in Kubernetes, whereas local Compose
uses `start-dev` and a development file database. Kubernetes still uses
the localhost HTTP hostname and OIDC issuer for port-forward access.
The frontend also targets Keycloak at `http://localhost:8080`.
Argo CD's LAN HTTPS setup does not expose this application or Keycloak.

The API image uses UID/GID 10001, a read-only root filesystem, no added
capabilities, disabled privilege escalation, `RuntimeDefault` seccomp,
and no automatic ServiceAccount token mount. Startup and liveness probes
use `/healthz`; readiness uses `/readyz`. Database credentials come from
the separately provisioned `promotion-database` Secret.

The recorded Kubernetes browser checks include writes that had not been
repeated in the earlier local Compose validation: developer creation,
approval, rejection, and reader inspection. PostgreSQL Pod replacement
preserved records using the same PVC. This does not establish node-loss
recovery or backup restoration.

See [GitOps operations](../gitops/README.md) for localhost port-forwards,
initialization, and Secret provisioning boundaries.

## Delivery milestones

Completed:

1. Domain rules and PostgreSQL persistence.
2. Concurrency protection and database permission checks.
3. HTTP endpoints and role-based authorization.
4. Keycloak integration and token validation.
5. Fresh realm import validation.
6. Browser frontend and manual role-based workflow validation.
7. Container image build and local execution of the API and compiled frontend.
8. CI tests, secret scanning, SAST, dependency auditing, and image scanning.
9. GHCR publication, keyless Cosign signing, and signature verification.
10. Kubernetes deployment through Argo CD with digest-pinned images.
11. Namespace image admission, including init and ephemeral containers.
12. Kubernetes browser workflow and PostgreSQL Pod-replacement persistence checks.

Next:

1. Extend LAN HTTPS to the API/frontend and Keycloak.
2. Add database, identity-provider, and browser integration checks to CI.
3. Validate workload isolation, secret rotation, and backup restoration.

Automated tests use controlled identities and mocked dependencies where
appropriate. These test mechanisms do not provide an authentication
bypass in the running application.

## Later extensions

- Record and verify build provenance, scan evidence, and SBOM references
  associated with promotion requests.
- Use pipeline identities to submit promotion requests.
- Connect recorded approvals to reviewed GitOps release updates.
- Validate workload isolation, secret rotation, and recovery.

These extensions are planned and are not implemented capabilities.
