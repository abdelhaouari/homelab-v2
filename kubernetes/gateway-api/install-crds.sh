#!/usr/bin/env bash
set -euo pipefail

# Install the standard Gateway API CRDs required by Cilium 1.20.4.
version="v1.6.3"
base_url="https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/${version}/config/crd/standard"
download_dir="$(mktemp -d /tmp/homelab-gateway-api.XXXXXX)"

resources=(
  gatewayclasses
  gateways
  httproutes
  referencegrants
  grpcroutes
  backendtlspolicies
  tlsroutes
)

printf 'Gateway API version: %s\n' "$version"
printf 'Downloaded manifests: %s\n' "$download_dir"

# Download every manifest before making any cluster changes.
for resource in "${resources[@]}"; do
  filename="gateway.networking.k8s.io_${resource}.yaml"
  curl --fail --silent --show-error --location \
    "${base_url}/${filename}" \
    --output "${download_dir}/${filename}"
done

kubectl apply --server-side --dry-run=server -f "$download_dir"
kubectl apply --server-side -f "$download_dir"

for resource in "${resources[@]}"; do
  kubectl wait --for=condition=Established \
    "crd/${resource}.gateway.networking.k8s.io" \
    --timeout=60s
done

printf 'Gateway API CRDs installed and established.\n'
