# GitOps validation schemas

These schema snapshots support cluster-independent manifest validation.

## Sources

Native schemas:

- Source: https://github.com/yannh/kubernetes-json-schema
- Directory: v1.36.0-standalone-strict
- Kubernetes minor version: 1.36
- Files are committed locally rather than fetched during validation.

Custom schemas were converted from the installed CRDs:

- Argo CD: v3.5.6
- Cilium: 1.20.4
- Kyverno: v1.19.2
- Gateway API: v1.6.3
- cert-manager: v1.21.3

Conversion used scripts/openapi2jsonschema.py from yannh/kubeconform
tag v0.8.0, with FILENAME_FORMAT={fullgroup}-{kind}_{version}.

Only schemas required by the current validation scope and the planned
HTTPRoute resources are included.

SHA256SUMS records the committed JSON file contents. It detects accidental
changes but is not an independent authenticity or security guarantee.

## Maintenance

Review schema updates alongside controller, CRD, or Kubernetes upgrades.
Regenerate SHA256SUMS after reviewing changed schema files.

Missing schemas fail validation. Do not bypass them with
ignore-missing-schemas.

## Limits

JSON Schema validation does not execute admission webhooks or Kubernetes CEL
validation rules. It does not verify RBAC permissions, referenced object
existence, image signatures, or runtime connectivity.

Converted custom schemas do not reproduce every API-server validation.
Cluster-side admission and functional checks remain necessary.

The current scope covers GitOps Applications, AppProjects, Kustomize bundles,
and selected bootstrap manifests. It does not validate Helm values or every
standalone manifest under kubernetes/.
