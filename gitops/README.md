# GitOps application deployments

This directory contains the deployment configuration for applications
intended to be managed by Argo CD in Homelab V2.

Application source code lives in `../app/`.
Cluster bootstrap configuration and platform tests also exist in
`../kubernetes/`; they are not automatically managed by Argo CD.

## Current status

- Argo CD is installed with versioned Helm values.
- The ApplicationSet controller is scaled to zero.
- The GitOps directory structure is prepared.
- AppProjects and the root Application are defined and passed server-side
  dry-run validation. They have not been applied yet.
- The promotion stack is not deployed through Argo CD yet.

Directory contents alone do not enable reconciliation. Argo CD only
manages resources selected by a configured Application.

## Directory structure

```text
gitops/
├── README.md
├── bootstrap/
│   └── argocd/
│       └── values.yaml
├── projects/
├── apps/
└── manifests/
    └── promotion/
        ├── namespace.yaml
        └── init-postgres.sh
```

| Directory | Purpose |
|-----------|---------|
| `bootstrap/` | Configuration used to establish GitOps management |
| `projects/` | AppProjects defining permitted sources, destinations and resource types |
| `apps/` | Child Application definitions |
| `manifests/` | Kubernetes resources and configuration inputs for each application |

The `projects/` directory contains `gitops-admin.yaml` and `workloads.yaml`.
The `apps/kustomization.yaml` file explicitly selects child Applications;
its resource list is currently empty.
The root Application is defined in `bootstrap/root-application.yaml`.

## Target reconciliation model

The intended design uses the app-of-apps pattern:

```text
Root Application
  -> gitops/apps/
     -> promotion Application
        -> gitops/manifests/promotion/
     -> future application
        -> gitops/manifests/<application>/
```

The root Application manages child Application resources.
Each child Application manages its own workloads.

One Application may represent a complete stack, including several
Deployments, StatefulSets and Services.

ApplicationSet is not required for this design.

## Ownership and permissions

The root Application has an administrative role because it manages
other Applications. Changes to its configuration and to `apps/` require
careful review.

Workload Applications must use an explicitly configured AppProject.
Allowed repositories, destinations and resource types must reflect
their actual requirements.

Applications should use dedicated namespaces. Namespace separation
does not replace RBAC or network policies.

Platform components and application workloads have separate ownership.
Do not manage the same resource through independent Helm releases,
manual manifests and Argo CD Applications.

## Adding an application

Once the root Application is configured:

1. Create `manifests/<application>/`.
2. Add the workload manifests and a `kustomization.yaml`.
3. Check that the intended AppProject permits the deployment.
4. Add `apps/<application>.yaml` with the repository, revision,
   source path, destination and project. Register this file in
   `apps/kustomization.yaml`.
5. Render the manifests locally:

   ```bash
   kubectl kustomize gitops/manifests/<application>/
   ```

6. Review the diff, stage the intended files, commit and push.
7. Synchronize through Argo CD according to the configured sync policy.
8. Verify Application status and test the deployed service.

Rendering validates manifest assembly, not runtime behavior.
Replace `<application>` with the actual directory name.

## Synchronization and deletion

Sync policies must be explicit for each Application.

- Automated sync applies eligible Git changes without a manual sync.
- Self-heal can reconcile tracked resources that drift from Git.
- Pruning can delete tracked resources removed from Git.
- Application deletion finalizers can trigger cascading deletion.

Do not enable deletion behavior without considering namespaces,
PersistentVolumeClaims and application data.

Git history is not a database backup. Storage retention is not a backup
or a high-availability mechanism.

## Secrets

Never commit plaintext Secret manifests, credentials, tokens or private
password files. Base64 encoding does not encrypt a Kubernetes Secret.

The existing `postgres-bootstrap` Secret is currently provisioned
outside GitOps. Recreating the cluster requires provisioning it again
before starting PostgreSQL.

Encrypted or external secret management is not configured yet.

## Images and security boundaries

The promotion application image is built, tested, scanned, published
to GHCR and signed by CI. Deployment configuration should reference
the verified image digest.

The existing Kyverno signature policy is enforced in `signature-test`.
It does not yet enforce signatures in the promotion namespace.

A valid signature identifies an accepted signer and image digest.
It does not prove that the image has no vulnerabilities.

See [container security](../docs/container-security.md) for the scan
policy, documented exceptions and signature verification evidence.

## Scope and limitations

This repository keeps application code and deployment configuration
together to make the homelab easier to reproduce.

Argo CD currently runs without high availability.
Local-path storage is node-local and does not replicate application data.

Bootstrap procedures, secret provisioning and recovery steps must
remain documented alongside the deployment configuration.

## Bootstrap ownership

Argo CD installation, AppProjects and application namespaces are
provisioned explicitly during bootstrap.

The root Application watches only `gitops/apps/`. It does not manage
the AppProjects, its own definition or the Argo CD Helm release.

The `gitops-admin` project permits Application resources in `argocd`.
This remains an administrative capability: changes to child Application
definitions must be reviewed by trusted maintainers.

The `workloads` project currently permits selected namespaced resource
types in `promotion`. Additional application namespaces must be
explicitly authorized before deployment.

Cluster-scoped resources are not permitted by either project.
The promotion Namespace manifest is a bootstrap input and must not be
included in the workload Kustomize resource list.

Plaintext Secrets are provisioned separately and are not permitted as
managed resources by the current workloads project.

## Initial root sync policy

The root Application enables automated synchronization and self-heal.
Automatic pruning is disabled, and no cascading-deletion finalizer is
configured on the root Application.

Removing a child Application from Git will therefore require an
explicit cleanup decision. Each child Application defines its own
workload synchronization and deletion policy.

Publish the configuration to Git before applying the root Application,
because Argo CD reads the remote repository rather than local files.
