# Application container security

## Scope

This assessment covers the promotion application runtime image based on
python:3.12-slim-trixie, with Debian package updates applied during build.

It does not cover the PostgreSQL or Keycloak images, the container host,
or images referenced by promotion requests.

Assessment date: 2026-10-26.
Exception review deadline: 2026-11-09.
Owner: repository maintainer.
Deployment scope: local homelab only.

## Observed results

| Runtime image                 | HIGH findings | CRITICAL findings |
| ----------------------------- | ------------: | ----------------: |
| Bookworm with package updates |            59 |                 2 |
| Trixie with package updates   |            44 |                 0 |

The Trixie findings represent eight distinct CVEs.
These counts are scan observations, not counts of exploitable API flaws.

The Trixie candidate passed:

- Application liveness.
- PostgreSQL readiness.
- Rejection of unauthenticated identity requests.
- Browser authentication, request listing and request details.

## Verified runtime restrictions

- UID and GID: 10001.
- All process capability sets: zero.
- NoNewPrivs: 1.
- Privileged container: false.
- Read-only root filesystem.
- All Docker capabilities dropped.

These restrictions are mandatory for exceptions based on reduced privilege.
Equivalent controls must be validated before any Kubernetes deployment.
The image alone does not enforce all these restrictions.

## Temporary exceptions

| CVE            | Assessment and justification                                                                                                                                                           |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CVE-2026-16742 | The advisory targets systemd-homed. No systemd-homed executable was found under /usr, /bin or /sbin. The detected packages are libsystemd0 and libudev1.                               |
| CVE-2026-9538  | The advisory targets Perl Archive::Tar. No Archive/Tar.pm file was found under the inspected directories. The detected package is perl-base.                                           |
| CVE-2025-69720 | infocmp is present. No explicit invocation was found in application source or scripts. Temporary risk acceptance for the homelab, not a claim that the vulnerable component is absent. |
| CVE-2026-76642 | Privileged mount-helper scenario. Temporarily accepted under the verified runtime restrictions, with no explicit application mount invocation identified.                              |
| CVE-2026-78408 | Privileged nsenter --join-cgroup scenario. No explicit application invocation identified. Privileged administrative use of this image is outside this exception.                       |
| CVE-2026-78409 | Restricted mount scenario involving X-mount.subdir. Temporarily accepted under the verified runtime restrictions.                                                                      |
| CVE-2026-78410 | Restricted bind-mount scenario involving privileged ownership or mode changes. Temporarily accepted under the verified runtime restrictions.                                           |
| CVE-2026-54369 | Privileged pathname-based ACL operation. Temporarily accepted under the verified runtime restrictions, with no explicit application ACL manipulation identified.                       |

Source searches are supporting evidence, not exhaustive dependency analysis.
File searches establish absence only within the inspected locations.
Runtime mitigations do not fix vulnerable packages.

Debian advisories:
https://security-tracker.debian.org/tracker/CVE-2026-16742
https://security-tracker.debian.org/tracker/CVE-2026-9538
https://security-tracker.debian.org/tracker/CVE-2025-69720
https://security-tracker.debian.org/tracker/CVE-2026-76642
https://security-tracker.debian.org/tracker/CVE-2026-78408
https://security-tracker.debian.org/tracker/CVE-2026-78409
https://security-tracker.debian.org/tracker/CVE-2026-78410
https://security-tracker.debian.org/tracker/CVE-2026-54369

## Scan policy

- Scan the final application image.
- Block HIGH and CRITICAL findings unless covered by an unexpired,
  package-scoped exception.
- Do not globally ignore unfixed vulnerabilities.
- Keep unfiltered findings available for review.
- Treat scanner errors as failures.
- Reassess exceptions when packages, application behavior or runtime
  restrictions change.
- Apply available fixes and remove obsolete exceptions.
- Do not automatically extend exception deadlines.
- Reassess all exceptions before Kubernetes deployment.

A passing gate means that no unexcepted HIGH or CRITICAL findings remain.
It does not mean that the image has no vulnerabilities.

## Kubernetes admission validation

Validated on 2026-10-26 with:

- Kubernetes v1.36.5.
- Kyverno v1.19.2, Helm chart 3.9.2.
- Cosign v3.1.4 signing in GitHub Actions.
- Public image and signature storage in GHCR.

The ImageValidatingPolicy is restricted to the signature-test namespace.

Server-side dry-run results:

- Signed image with the expected workflow identity: accepted.
- Unsigned image: denied by the image verification policy.
- Signed image with a deliberately incorrect expected identity: denied.

The expected identity was restored after testing:
https://github.com/abdelhaouari/homelab-v2/.github/workflows/ci.yml@refs/heads/main

These tests validate admission behavior, not application runtime.
Kubernetes v1.36 is outside the published Kyverno v1.19 support matrix.
This is a successful homelab compatibility test, not an upstream support claim.

## Promotion namespace image admission

Two ImageValidatingPolicy resources enforce image admission in `promotion`:

| Policy | Scope |
|--------|-------|
| `verify-promotion-workloads` | Pods and automatically generated controller rules |
| `verify-promotion-workloads-ephemeral` | Updates through `pods/ephemeralcontainers` |

The policies are applied explicitly from `kubernetes/kyverno/`.
They are not managed by the workloads Argo CD Application.

### Trust rules

Application images must reference
`ghcr.io/abdelhaouari/homelab-v2@sha256:<digest>` and pass keyless
signature verification with:

- Issuer: `https://token.actions.githubusercontent.com`
- Identity: `https://github.com/abdelhaouari/homelab-v2/.github/workflows/ci.yml@refs/heads/main`

PostgreSQL and Keycloak are admitted through an exact image-reference
allowlist containing their validated digests. Their vendor signatures
are not verified by these policies.

Other image references are denied. Updating a vendor image requires
reviewing and updating both policies as well as its workload manifest.

The allowlist applies throughout the namespace. It does not bind an
approved image to a specific Deployment or container name.

### Configuration details

Both policies use `Deny` and `failurePolicy: Fail`.
Image references are not automatically rewritten to digests.

`required: false` disables the additional requirement that every image
undergo signature or attestation verification. The CEL expression still
requires signature verification for application images and permits only
the exact vendor image references otherwise.

The expression combines ordinary, init and ephemeral container images.
Checking only `images.containers` did not cover init containers.

Matching `pods` and `pods/ephemeralcontainers` together resulted in no
generated controller configurations in the tested installation.
Separate policies restored Deployment admission checks while preserving
ephemeral-container checks.

### Observed admission tests

All tests used server-side dry-run; no test workload or ephemeral
container was created.

| Test | Observed result |
|------|-----------------|
| Pod with signed application image | Allowed |
| Pod with approved PostgreSQL digest | Allowed |
| Pod with approved Keycloak digest | Allowed |
| Pod with unsigned application digest | Denied |
| Pod with an unapproved tag-only image | Denied for missing digest |
| Signed application with forbidden digest-pinned init container | Denied |
| Signed application with signed init container | Allowed |
| Deployment with signed application image | Allowed |
| Deployment with forbidden digest-pinned image | Denied |
| Signed ephemeral container | Allowed |
| Forbidden digest-pinned ephemeral container | Denied |

Negative tests checked the policy denial message rather than treating
every nonzero command exit code as a successful security test.

### Limits

Background evaluation is disabled. Installing a policy does not evict
existing Pods or prove that every running workload was admitted under it.

Deployment admission was tested explicitly. Other generated controller
types were not individually tested.

These checks do not prove vulnerability freedom, runtime isolation,
backup readiness or protection against a cluster administrator who can
modify the policies.

Keep both policies' trust rules synchronized when changing the allowlist
or accepted signing identity.
