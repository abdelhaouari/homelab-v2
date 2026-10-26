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
