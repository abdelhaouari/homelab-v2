#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

kubectl_bin="${KUBECTL_BIN:-kubectl}"
kubeconform_bin="${KUBECONFORM_BIN:-kubeconform}"

command -v "$kubectl_bin" >/dev/null
command -v "$kubeconform_bin" >/dev/null

# Validate the exact schema snapshot committed in this repository.
(
  cd ci/schemas
  sha256sum --check SHA256SUMS
)

render_dir="$(mktemp -d "${TMPDIR:-/tmp}/homelab-gitops-render.XXXXXX")"
printf 'Rendered manifests: %s\n' "$render_dir"

# Local rendering only. No Kubernetes API request is made.
"$kubectl_bin" kustomize gitops/apps > "$render_dir/applications.yaml"

bundle_count=0
for directory in gitops/manifests/*/; do
  if [[ -f "${directory}kustomization.yaml" ||
        -f "${directory}kustomization.yml" ||
        -f "${directory}Kustomization" ]]; then
    name="$(basename "$directory")"
    "$kubectl_bin" kustomize "$directory" > "$render_dir/bundle-$name.yaml"
    bundle_count=$((bundle_count + 1))
  fi
done

if [[ "$bundle_count" -eq 0 ]]; then
  printf 'No workload Kustomize bundles found.\n' >&2
  exit 1
fi

for manifest in gitops/projects/*.yaml; do
  cp "$manifest" "$render_dir/project-$(basename "$manifest")"
done

# Bootstrap manifests are validated even though Argo CD does not manage them.
for manifest in gitops/bootstrap/*.yaml; do
  cp "$manifest" "$render_dir/bootstrap-$(basename "$manifest")"
done

cp gitops/manifests/promotion/namespace.yaml \
  "$render_dir/promotion-namespace.yaml"

for manifest in "$render_dir"/*.yaml; do
  if [[ ! -s "$manifest" ]]; then
    printf 'Empty manifest: %s\n' "$manifest" >&2
    exit 1
  fi
done

"$kubeconform_bin" \
  -strict \
  -summary \
  -verbose \
  -kubernetes-version 1.36.0 \
  -schema-location "$repo_root/ci/schemas/custom/{{.Group}}-{{.ResourceKind}}_{{.ResourceAPIVersion}}.json" \
  -schema-location "$repo_root/ci/schemas/native/{{.ResourceKind}}{{.KindSuffix}}.json" \
  "$render_dir"
