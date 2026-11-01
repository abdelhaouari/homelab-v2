# GitOps workloads and platform services

Argo CD manages the promotion application stack, image admission policies,
LAN address allocation, shared Gateway, certificate issuers, and Argo CD
routes from this directory using the app-of-apps pattern.

Application source code lives in `../app/`. Cluster bootstrap resources
and platform tests also exist in `../kubernetes/`; they are not
automatically managed by Argo CD.

## Validated state

- All seven Argo CD Applications were `Synced` and `Healthy` during
  the October 31, 2026 read-only review.
- PostgreSQL, Keycloak and the promotion API are running in Kubernetes.
- The API serves the compiled frontend.

Earlier functional validations recorded in this repository include:

- Browser authentication through Keycloak works.
- A developer created promotion requests.
- An approver approved one request and rejected another.
- A reader viewed an approved request.
- PostgreSQL data survived replacement of its Pod using the same PVC.
- The application database role authenticated over TCP and read its table.
- The Keycloak database role authenticated over TCP.
- Image admission allowed the signed application and approved vendor
  digests, and denied unauthorized images, including init/ephemeral containers.
- Argo CD LAN HTTPS, HTTP redirection, and browser login worked through
  the shared Gateway with a production certificate.

These observations validate the tested paths. They do not demonstrate
high availability, node-loss recovery or a complete fresh-cluster rebuild.
UI visibility alone does not prove server-side authorization enforcement.

The application records promotion decisions. Approving a request does
not deploy an image or verify its signature.

## Directory structure

```text
gitops/
├── README.md
├── bootstrap/
│   ├── ingress-namespace.yaml
│   ├── root-application.yaml
│   └── argocd/
│       └── values.yaml
├── projects/
│   ├── gitops-admin.yaml
│   ├── platform-*.yaml
│   └── workloads.yaml
├── apps/
│   ├── kustomization.yaml
│   └── *.yaml                 # Six child Applications
└── manifests/
    ├── promotion/
    ├── kyverno-policies/
    ├── network-infrastructure/
    ├── shared-gateway/
    ├── certificate-infrastructure/
    └── argocd-routing/
```

Kustomize also uses `app/sql/` and `app/keycloak/` from the repository
root to generate ConfigMaps from the existing SQL scripts and realm
configuration. These source files are not duplicated.

## Reconciliation model

```text
GitHub repository, main branch
  -> homelab-apps Application
     -> gitops/apps/kustomization.yaml
        -> promotion                  -> API/frontend, Keycloak, PostgreSQL
        -> kyverno-policies           -> ImageValidatingPolicy resources
        -> network-infrastructure     -> Cilium IP pool and L2 policy
        -> shared-gateway             -> Gateway and Certificates
        -> certificate-infrastructure -> Staging/production ClusterIssuers
        -> argocd-routing             -> HTTPS route and HTTP redirect
```

The root Application manages child Application resources. Each child
Application manages the resources selected by its source configuration.

Adding a YAML file does not necessarily deploy it: register it in the
appropriate `kustomization.yaml`.

ApplicationSet is not required for this design; its controller is
scaled to zero.

## Bootstrap and ownership

Argo CD is installed with Helm using versioned values.
AppProjects, application namespaces and Secrets are provisioned
explicitly during bootstrap.

The root Application does not manage its own definition, the AppProjects,
the controller Helm releases, the Gateway API CRDs, the local-path
provisioner, namespaces, or bootstrap Secrets.

| Project        | Destination | Allowed resources                           |
| -------------- | ----------- | ------------------------------------------- |
| `gitops-admin` | `argocd`    | Child Applications                          |
| `workloads`    | `promotion` | Explicitly listed namespaced workload types |
| `platform-security` | `kyverno` | Cluster-scoped ImageValidatingPolicy only |
| `platform-network` | `kube-system` | Cluster-scoped CiliumLoadBalancerIPPool and CiliumL2AnnouncementPolicy only |
| `platform-gateway` | `ingress-system` | Gateway, HTTPRoute, and Certificate |
| `platform-certificates` | `cert-manager` | Cluster-scoped ClusterIssuer only |
| `platform-argocd-routing` | `argocd` | HTTPRoute only |

Each project restricts the source repository, destinations, and resource
types. The three projects managing cluster-scoped resources deny all
namespaced types. The promotion Namespace manifest is a bootstrap input,
excluded from the workload Kustomize resource list.

Bootstrap dependencies must exist before their child Applications sync:

1. Install the platform controllers and Gateway API CRDs separately.
   Gateway API CRDs precede Cilium with Gateway API enabled.
2. Prepare local-path storage, application/ingress namespaces, and Secrets.
3. Apply the required AppProjects from `gitops/projects/`.
4. Apply the root Application from `gitops/bootstrap/root-application.yaml`.
5. Check child synchronization. Address allocation and certificate issuance
   must be ready for the Gateway and HTTPS routes to become usable.

This is dependency ordering; the repository does not contain one command
that reproduces the full platform and recovers its data. Controller and
service ownership is described in [architecture](../docs/architecture.md).

Managing Applications in `argocd` is an administrative capability.
Changes to `apps/`, projects and bootstrap configuration require review
by trusted maintainers.

Do not manage the same resource through independent Helm releases,
manual manifests and Argo CD Applications.

## Adding an application

Run repository commands from the repository root.

1. Create `gitops/manifests/<application>/`.
2. Add its manifests and `kustomization.yaml`.
3. Provision its namespace and required Secrets separately.
4. Explicitly authorize its namespace and required resource types in
   the appropriate AppProject.
5. Create `gitops/apps/<application>.yaml` with the repository, revision,
   source path, project and destination.
6. Register the Application in `gitops/apps/kustomization.yaml`.
7. Render, validate with the repository's pinned-schema tooling, and
   check cluster admission:

   ```bash
   kubectl kustomize gitops/manifests/<application>/
   bash ci/scripts/validate-gitops.sh
   python3 ci/scripts/test-gitops-validator.py
   kubectl apply --dry-run=server -k gitops/manifests/<application>/
   kubectl apply --dry-run=server -k gitops/apps/
   ```

8. Review the changes, stage the intended files, commit and push.
9. Check Argo CD status and test the deployed service.

Replace `<application>` with the actual directory name.
The local validation commands require kubectl and kubeconform as described
in [secure delivery](../docs/delivery.md).
Rendering and server dry-runs do not prove successful runtime behavior.

## Synchronization and deletion

All seven Applications enable automated sync and self-heal.
Automatic pruning is disabled, and none has a cascading-deletion finalizer.

Removing resources from Git therefore requires an explicit cleanup
decision. Old generated ConfigMaps can remain when their content hash
changes; remove them only after checking that they are no longer used.

The PostgreSQL PVC has `Prune=false,Delete=false` Argo CD annotations.
These do not protect it against direct deletion through Kubernetes.

Self-heal reconciles tracked configuration. It does not restore deleted
database contents or replace access controls.

## Secrets and initialization

The following Secrets are provisioned outside GitOps:

| Secret                     | Consumer   | Purpose                                    |
| -------------------------- | ---------- | ------------------------------------------ |
| `postgres-bootstrap`       | PostgreSQL | Initial database and role passwords        |
| `keycloak-database`        | Keycloak   | Password for the Keycloak database role    |
| `keycloak-bootstrap-admin` | Keycloak   | Initial administrator credentials          |
| `promotion-database`       | API        | Password for the application database role |

Never commit plaintext Secret manifests, tokens or password files.
Base64 encoding is not encryption. Local private files are excluded
from Git but are not an encrypted secret store.

Rebuilding the cluster requires provisioning these Secrets again.
Encrypted or external secret management is not configured.

The certificate platform also requires `cloudflare-api-token-secret` in
`cert-manager`. Its provisioning is documented in the
[cert-manager guide](../kubernetes/cert-manager/README.md). ACME account
keys and certificate Secrets are generated by cert-manager.

PostgreSQL initialization scripts run only on an empty data directory.
Changing their ConfigMaps does not migrate an existing database or
rotate existing role passwords.

Keycloak imports the realm when it is absent. Changing the import file
does not reconcile an existing realm. Test users were created separately
and are stored in PostgreSQL, not in Git.

Bootstrap administrator credentials are for initial setup. Establishing
a permanent administrator and removing the temporary bootstrap account
remains a follow-up task.

## Application access

The promotion application and Keycloak use HTTP through localhost
port-forwards. Argo CD uses [LAN HTTPS](manifests/argocd-routing/README.md).
From the repository root, select the lab kubeconfig:

```bash
export KUBECONFIG="$PWD/private/homelab-v2.kubeconfig"
```

Keep each command running in its own WSL terminal:

```bash
kubectl -n promotion port-forward \
  --address 127.0.0.1 service/keycloak 8080:8080
```

```bash
kubectl -n promotion port-forward \
  --address 127.0.0.1 service/promotion-api 8000:8000
```

Open the application at `http://localhost:8000`.
The Keycloak administration console is at `http://localhost:8080/admin/`.

Stop conflicting local Compose services if they occupy these ports.
Each terminal running kubectl must use the intended kubeconfig.

The browser-facing issuer is `http://localhost:8080/realms/homelab`.
The API retrieves public signing keys through the internal
`http://keycloak:8080` Service address.

## Verification

```bash
kubectl -n argocd get applications
kubectl -n promotion get deployments,statefulsets,pods,pvc,services

curl --include http://localhost:8000/healthz
curl --include http://localhost:8000/readyz
curl --include http://localhost:8000/me
```

Expected unauthenticated HTTP results:

| Endpoint   | Expected result                          |
| ---------- | ---------------------------------------- |
| `/healthz` | `200`, API responds                      |
| `/readyz`  | `200`, database readiness check succeeds |
| `/me`      | `401`, Bearer authentication required    |

Use separate authenticated sessions to test developer creation,
approver approval and rejection, and reader access. Verify the role
displayed by the API after each account change.

## Images and security boundaries

The application image was built, tested, scanned, published to GHCR,
signed by CI and independently verified. Its Deployment uses the
verified digest. PostgreSQL and Keycloak are also pinned by digest.

Kyverno enforces image admission in `promotion`:
- Application images must use a digest and a valid signature from the
  homelab-v2 CI workflow on main.
- PostgreSQL and Keycloak are allowed only at explicitly approved digests.
- Other images are denied.

Separate policies cover Pods and generated controller rules, and the
`pods/ephemeralcontainers` subresource. The original policy remains in
`signature-test`.

The `kyverno-policies` Application manages these platform policies from
`gitops/manifests/kyverno-policies/` through the `platform-security`
AppProject. The root `homelab-apps` Application manages this child
alongside the five other workload and platform Applications.

The policies use automated synchronization with self-healing enabled
and pruning disabled. Removing a policy from Git does not automatically
delete it from the cluster.

Bootstrap the security project before synchronizing its Application:

```bash
kubectl apply -f gitops/projects/platform-security.yaml
```

The Kyverno controllers remain installed separately with Helm using
`kubernetes/kyverno/values.yaml`.

A valid signature identifies an accepted signer and image digest.
It does not prove that an image has no vulnerabilities.

The API runs as UID 10001 with a read-only root filesystem, dropped
capabilities and privilege escalation disabled.

Keycloak runs as UID 1000 with dropped capabilities and privilege
escalation disabled. Its filesystem remains writable because the
official image performs startup augmentation. A preoptimized image
is a future improvement.

See [container security](../docs/container-security.md) for scan policy,
risk exceptions and signature verification evidence.

## Limits and remaining work

- The promotion application and Keycloak still use localhost HTTP
  port-forwards. Argo CD LAN HTTPS is configured and validated.
- PostgreSQL and Keycloak each run as a single instance.
- Argo CD is not deployed in high-availability mode.
- Local-path storage is node-local and does not replicate data.
- PVC capacity requests are not guaranteed filesystem quotas.
- Pod replacement persistence was tested; node-loss recovery and
  backup restoration were not.
- The manifests currently define no application-specific NetworkPolicy.
- A complete fresh-cluster reproduction remains to be validated.
- Secret provisioning and recovery need a consolidated runbook.

Git history and volume retention are not database backups.
