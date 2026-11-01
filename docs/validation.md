# Validation record and current state

This record separates the state observed during the October 31, 2026
documentation review from earlier functional tests documented in the
repository. It is a dated snapshot of a personal homelab.

## Cluster state observed on October 31, 2026

The review queried the existing cluster in read-only mode. It did not
redeploy workloads, replace Pods, change policies, or request certificates.

| Component | Observed state |
| --- | --- |
| Kubernetes | `k8s-cp01` and all three workers `Ready`, Kubernetes `v1.36.5`, containerd `2.2.1` |
| Argo CD | All seven Applications `Synced` and `Healthy` |
| Application | `promotion-api` Deployment `1/1` available |
| Identity | `keycloak` Deployment `1/1` available |
| Database | `postgres` StatefulSet `1/1` ready; `postgres-data` PVC bound, 5 GiB, `local-path` |
| Shared Gateway | `homelab-gateway`, class `cilium`, address `10.10.20.103`, `Programmed=True` |
| Certificates | `argocd` and `argocd-staging` both ready in `ingress-system` |
| ACME issuers | `letsencrypt-prod` and `letsencrypt-staging` both ready |
| Image policies | All three `ImageValidatingPolicy` resources report ready |
| Helm releases | Argo CD `10.11.6` / `v3.5.6`; Cilium `1.20.4`; Kyverno `3.9.2` / `v1.19.2`; cert-manager `v1.21.3` |

The seven Applications are `homelab-apps`, `promotion`, `kyverno-policies`,
`network-infrastructure`, `shared-gateway`, `certificate-infrastructure`,
and `argocd-routing`.

These statuses establish controller-reported readiness and reconciliation.
They do not repeat the historical functional tests below.

## Local checks during the documentation review

- All 38 service-independent application tests passed: domain, liveness,
  readiness, API authentication, HTTP routes, and CLI ID-token validation.
- All seven Kustomize entry points rendered: child Applications and six
  workload/platform bundles.
- All committed schema checksums matched `ci/schemas/SHA256SUMS`.
- Relative Markdown links resolved and code fences were balanced.
- `git diff --check` found no whitespace errors.

The local Kustomize and checksum checks do not constitute a new full
kubeconform run. Database integrations, browser tests, image scans, and
admission dry-runs were not repeated during this review.

## Recorded functional evidence

| Area | Result recorded in the repository | Evidence and scope |
| --- | --- | --- |
| Provisioning | Disposable VM recreation; four cluster VMs provisioned | [Proxmox notes](proxmox-bootstrap.md); full cluster reconstruction remains untested |
| Configuration | Consolidated Ansible rerun with zero changes and no failures | [Rebuild guide](rebuild.md); convergence against the existing deployment |
| Networking | DNS, cross-node HTTP, and ClusterIP HTTP succeeded; Service paths checked after kube-proxy removal | [Architecture](architecture.md); connectivity rather than isolation or performance |
| Application rules | Business rules, token validation, HTTP authorization, persistence, constraints, and concurrent decisions passed | [Application tests](application.md); mocked and database-backed suites have different scopes |
| Kubernetes application | Developer submission, approver approval/rejection, reader inspection, and browser login succeeded | [GitOps guide](../gitops/README.md); manually exercised workflows |
| Persistence | PostgreSQL data survived Pod replacement using the same PVC | [GitOps guide](../gitops/README.md); no node-loss or off-host restore test |
| Image admission | Signed application accepted; unsigned, incorrect signer, forbidden init/ephemeral images denied | [Security assessment](container-security.md); server-side dry-runs |
| DNS-01 and TLS | Staging and production certificates issued; HTTP redirected; HTTPS returned 200 with certificate verification; browser login succeeded | [Argo CD routing](../gitops/manifests/argocd-routing/README.md) and [cert-manager](../kubernetes/cert-manager/README.md); workstation LAN access |

The workstation's local DNS resolution and browser login were recorded
before this documentation review. A ready Certificate alone does not
establish either result. No automatic certificate renewal or Gateway
failover test is recorded.

## Recheck the reported cluster state

From the repository root, select the existing lab kubeconfig:

```bash
export KUBECONFIG="$PWD/private/homelab-v2.kubeconfig"

kubectl get nodes -o wide
kubectl -n argocd get applications
kubectl -n promotion get deployments,statefulsets,pods,pvc
kubectl -n ingress-system get gateways,certificates
kubectl -n argocd get httproutes
kubectl get clusterissuers,imagevalidatingpolicies
helm list --all-namespaces
```

Functional procedures are linked in the evidence table. Record the
expected response or denial reason; a generic command failure does not
establish that the intended security control worked.

## Remaining validation and engineering work

- Complete reconstruction from fresh VMs, including separately installed
  controllers, bootstrap resources, credentials, and application data.
- Off-host Terraform-state protection and database/identity restoration.
- Workload NetworkPolicy allow/deny tests and network isolation evidence.
- Node-loss behavior, Gateway announcement failover, and availability
  during maintenance.
- Automatic cert-manager and Hubble certificate renewal.
- Application and Keycloak LAN HTTPS, with matching OIDC issuer and
  browser configuration.
- PostgreSQL, real Keycloak, and browser integration checks in CI.
- SBOM/provenance evidence and approval-driven GitOps release selection.
- Consolidated secret provisioning, rotation, and recovery procedures.
- Platform metrics, dashboards, and alerting beyond enabled component
  settings; no complete observability stack is versioned in this repository.

These items are the next stage of the platform rather than completed
capabilities. Single-host infrastructure and node-local storage remain
explicit constraints.
