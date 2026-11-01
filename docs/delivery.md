# Secure delivery and image trust

The delivery path connects application checks, registry publication,
keyless signing, GitOps reconciliation, and Kubernetes image admission.
The implementation lives in [Application CI](../.github/workflows/ci.yml),
the [GitOps manifests](../gitops/), and the
[Kyverno policies](../gitops/manifests/kyverno-policies/).

## CI triggers and jobs

The workflow runs on pushes to `main`, pull requests targeting `main`,
and manual dispatch. Two jobs run independently on Ubuntu 24.04 runners:

| Job | Responsibility |
| --- | --- |
| `gitops` | Render GitOps bundles, validate against committed strict schemas, and confirm invalid resources are rejected |
| `validate` | Scan source and dependencies, run application tests, build and check the container, scan the final image, then publish and sign on a push to `main` |

Publication and signing require the event to be a push to `main`.
Pull requests and manual dispatches do not execute those steps.

The application job does not declare a dependency on the GitOps job.
A successful application job can publish even if manifest validation fails.
Repository branch protection and required checks are outside the versioned
workflow configuration; their enforcement has not been established here.

## Application checks

| Stage | Control |
| --- | --- |
| Secret detection | Gitleaks scans the full fetched Git history with output redaction |
| Python SAST | Bandit scans `app/src` and `app/scripts` at all severity and confidence levels |
| Python dependencies | `pip-audit --strict` audits development, CLI, and security requirements |
| JavaScript dependencies | `npm audit` checks the lockfile, including development dependencies, from severity low |
| Automated tests | Six suites cover domain rules, liveness, readiness, API authentication, routes, and CLI ID-token validation |
| Container build | Multi-stage build compiles the frontend and copies it into the Python runtime |
| HTTP checks | Liveness, compiled frontend delivery, and unauthenticated `/me` rejection |
| Runtime restrictions | Docker configuration and `/proc/1/status` checks verify UID/GID, capabilities, `NoNewPrivs`, and a read-only root filesystem |
| Image vulnerabilities | Trivy scans the final application image and blocks unexcepted HIGH/CRITICAL findings |

The six service-independent suites contain 38 tests. PostgreSQL repository,
SQL constraint, concurrent-transaction, and real Keycloak/browser checks
are separate validations; CI does not currently run those integrations.
The container smoke test starts without PostgreSQL or Keycloak and does
not establish database readiness or authenticated browser behavior.

Trivy first displays unfiltered HIGH/CRITICAL findings, then enforces the
package-scoped exceptions in [`.trivyignore.yaml`](../app/.trivyignore.yaml).
Exceptions have an expiry date and supporting rationale in the
[security assessment](container-security.md). Scanner failures fail the job.
A passing gate can include accepted findings covered by those exceptions.

GitHub Actions are pinned to commit SHAs; Gitleaks and Trivy images are
pinned by digest. Application base images use tags, and Python transitive
dependencies are not fully locked by hashes.

## Publication and keyless signing

After the preceding application checks succeed on a push to `main`:

1. CI authenticates to GHCR with the job's `GITHUB_TOKEN`.
2. It publishes `ghcr.io/abdelhaouari/homelab-v2:sha-<commit>`.
3. It resolves the published SHA-256 digest and signs that digest using
   Cosign `3.1.4` and the GitHub Actions OIDC identity.
4. It verifies the signature against the exact workflow identity and
   issuer, then writes the digest to the workflow summary.

The accepted identity is:

```text
Issuer:   https://token.actions.githubusercontent.com
Identity: https://github.com/abdelhaouari/homelab-v2/.github/workflows/ci.yml@refs/heads/main
```

The workflow requests `packages: write` and `id-token: write` for the
application job. Signing uses a short-lived OIDC identity without a
long-lived signing private key stored in the repository.

A signature establishes an accepted signer for a digest. The current
pipeline does not publish an SBOM or build-provenance attestation, and
admission does not inspect scan results or attestations.

## Release selection and reconciliation

The release is selected explicitly in
[`application.yaml`](../gitops/manifests/promotion/application.yaml) using
`ghcr.io/abdelhaouari/homelab-v2@sha256:<digest>`.
Publishing an image does not update that file. After a manifest change is
merged into `main`, Argo CD reconciles the selected revision.

The workflow contains no cluster deployment command or administrator
kubeconfig. Argo CD is responsible for applying the desired state inside
the cluster. Automated sync and self-healing are enabled; pruning is
disabled. See [GitOps operations](../gitops/README.md).

The promotion application stores human approval decisions independently
of this process. An approval currently causes no registry operation or
GitOps update.

## Admission trust boundary

Kyverno policies in `promotion` require:

- Application images at the repository's digest reference, verified
  against the exact CI issuer and workflow identity above.
- PostgreSQL and Keycloak images at the exact digests in the allowlist.
  Vendor signatures are not verified by these policies.
- Rejection of other image references, including unauthorized init and
  ephemeral container images.

Separate policies cover Pods and generated controller rules, and updates
through `pods/ephemeralcontainers`. They use `Deny`, `failurePolicy: Fail`,
and no background evaluation. Existing Pods are not evicted when a policy
is introduced. The allowlist applies across the namespace rather than
binding each image to a particular workload.

The [security assessment](container-security.md) records positive and
negative server-side admission tests and the compatibility limits of the
lab's Kyverno/Kubernetes combination.

## GitOps validation

[`validate-gitops.sh`](../ci/scripts/validate-gitops.sh) renders every
manifest bundle plus child Applications, AppProjects, and selected
bootstrap resources. It checks schema checksums and validates with
`kubeconform -strict`, using local native and CRD-derived schemas.
Missing schemas fail validation.

CI pins kubectl `1.35.3` and kubeconform `0.8.0`, with download checksums.
Rejection tests cover an unknown Service field, an invalid Gateway field
type, and an unknown resource without a schema.

With those tools on `PATH`, run from the repository root:

```bash
bash ci/scripts/validate-gitops.sh
python3 ci/scripts/test-gitops-validator.py
```

Schema validation is independent of cluster access. API-server admission,
reference resolution, credentials, and runtime connectivity require
separate checks. [Schema maintenance](../ci/schemas/README.md) describes
the snapshot sources and update procedure.
