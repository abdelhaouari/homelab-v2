# GitOps application deployments

Argo CD manages the promotion application stack from this directory
using the app-of-apps pattern.

Application source code lives in `../app/`. Cluster bootstrap resources
and platform tests also exist in `../kubernetes/`; they are not
automatically managed by Argo CD.

## Validated state

- Argo CD Applications `homelab-apps` and `promotion` reached
  `Synced` and `Healthy`.
- PostgreSQL, Keycloak and the promotion API are running in Kubernetes.
- The API serves the compiled frontend.
- Browser authentication through Keycloak works.
- A developer created promotion requests.
- An approver approved one request and rejected another.
- A reader viewed an approved request.
- PostgreSQL data survived replacement of its Pod using the same PVC.
- The application database role authenticated over TCP and read its table.
- The Keycloak database role authenticated over TCP.

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
│   ├── root-application.yaml
│   └── argocd/
│       └── values.yaml
├── projects/
│   ├── gitops-admin.yaml
│   └── workloads.yaml
├── apps/
│   ├── kustomization.yaml
│   └── promotion.yaml
└── manifests/
    └── promotion/
        ├── kustomization.yaml
        ├── namespace.yaml
        ├── init-postgres.sh
        ├── postgres.yaml
        ├── keycloak.yaml
        └── application.yaml
```

Kustomize also uses `app/sql/` and `app/keycloak/` from the repository
root to generate ConfigMaps from the existing SQL scripts and realm
configuration. These source files are not duplicated.

## Reconciliation model

```text
GitHub repository, main branch
  -> homelab-apps Application
     -> gitops/apps/kustomization.yaml
        -> promotion Application
           -> gitops/manifests/promotion/kustomization.yaml
              -> ConfigMaps, Services and PVC
              -> PostgreSQL StatefulSet
              -> Keycloak Deployment
              -> API and frontend Deployment
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
the Argo CD Helm release or the local-path provisioner.

| Project        | Destination | Allowed resources                           |
| -------------- | ----------- | ------------------------------------------- |
| `gitops-admin` | `argocd`    | Child Applications                          |
| `workloads`    | `promotion` | Explicitly listed namespaced workload types |

Neither project permits cluster-scoped resources. The promotion
Namespace manifest is a bootstrap input, excluded from the workload
Kustomize resource list.

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
7. Render and validate:

   ```bash
   kubectl kustomize gitops/manifests/<application>/
   kubectl apply --dry-run=server -k gitops/manifests/<application>/
   kubectl apply --dry-run=server -k gitops/apps/
   ```

8. Review the changes, stage the intended files, commit and push.
9. Check Argo CD status and test the deployed service.

Replace `<application>` with the actual directory name.
Rendering and server dry-runs do not prove successful runtime behavior.

## Synchronization and deletion

Both current Applications enable automated sync and self-heal.
Automatic pruning is disabled, and neither Application has a
cascading-deletion finalizer.

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

PostgreSQL initialization scripts run only on an empty data directory.
Changing their ConfigMaps does not migrate an existing database or
rotate existing role passwords.

Keycloak imports the realm when it is absent. Changing the import file
does not reconcile an existing realm. Test users were created separately
and are stored in PostgreSQL, not in Git.

Bootstrap administrator credentials are for initial setup. Establishing
a permanent administrator and removing the temporary bootstrap account
remains a follow-up task.

## Local access

The current setup uses HTTP through localhost port-forwards.
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

The Kyverno signature policy currently applies only to `signature-test`.
Signature enforcement in `promotion` is not configured yet.

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

- HTTP port-forwards are the current access method; durable HTTPS
  exposure is not configured.
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
