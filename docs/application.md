# Artifact promotion API

## Status

The Python domain layer and PostgreSQL persistence are implemented and
tested locally.

Completed:

- Promotion submission and approval/rejection rules.
- Role checks and prevention of self-approval or self-rejection.
- PostgreSQL schema with data consistency constraints.
- A restricted application database account.
- Parameterized queries for creation, retrieval, and decisions.
- Conditional updates preventing concurrent decisions from overwriting
  each other.

Observed validation:

- 10 domain unit tests passed.
- 10 PostgreSQL integration tests passed.
- 1 concurrent-decision test passed using two database connections.
- 5 SQL checks passed for valid requests and decision consistency.

The concurrency test forced both transactions to read a pending request.
One decision committed, the other raised a conflict, and a separate
connection retrieved the winning decision.

The HTTP API, OIDC authentication, application container, and CI/CD
pipeline are not implemented yet. Tests use synthetic application
identities and a local PostgreSQL instance.

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

## Proposed endpoints

| Method | Path                              | Purpose                              |
| ------ | --------------------------------- | ------------------------------------ |
| GET    | /health/live                      | Process liveness                     |
| GET    | /health/ready                     | Readiness, including database access |
| POST   | /promotion-requests               | Submit a request                     |
| GET    | /promotion-requests               | List requests                        |
| GET    | /promotion-requests/{id}          | Inspect a request                    |
| POST   | /promotion-requests/{id}/decision | Approve or reject a request          |

Health endpoints return minimal status information and no credentials
or internal configuration.

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
