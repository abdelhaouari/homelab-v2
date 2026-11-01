# Certificate management bootstrap

## Ownership

Helm manages cert-manager and its CRDs. The chart version and custom values
are stored in this directory.

Argo CD manages shared issuers through the certificate-infrastructure
Application. The platform-certificates AppProject is bootstrapped separately.

Cloudflare credentials are provisioned outside Git.

## Install cert-manager

Run from the repository root with the intended Kubernetes context selected:

```bash
helm upgrade --install cert-manager \
  oci://quay.io/jetstack/charts/cert-manager \
  --version "$(cat kubernetes/cert-manager/chart-version.txt)" \
  --namespace cert-manager \
  --create-namespace \
  --values kubernetes/cert-manager/values.yaml \
  --wait \
  --timeout 5m
```

The deployment uses one replica per component and is not highly available.
Resource requests and limits are initial homelab settings.

CRDs are retained when the Helm release is uninstalled. This retention
setting is not a backup mechanism.

## Prepare Cloudflare credentials

Create a dedicated API token with:

- Zone / DNS / Edit
- Zone / Zone / Read
- Zone resources restricted to ahaouari.com

These permissions allow DNS changes throughout the selected zone.

Store the token in a password manager. Create the Kubernetes Secret using
hidden terminal input, without placing the token in shell arguments or Git:

```bash
(
  set +x
  set -euo pipefail
  umask 077

  token_file="$(mktemp /tmp/homelab-cloudflare-token.XXXXXX)"
  trap 'rm -f -- "$token_file"; unset cloudflare_token' EXIT

  read -r -s -p 'Cloudflare API token (hidden): ' cloudflare_token
  printf '\n'

  if [[ -z "$cloudflare_token" ]]; then
    printf 'Token must not be empty.\n' >&2
    exit 1
  fi

  printf '%s' "$cloudflare_token" > "$token_file"
  unset cloudflare_token

  kubectl -n cert-manager create secret generic \
    cloudflare-api-token-secret \
    --from-file="api-token=$token_file"
)
```

This command creates a new Secret; it is not a credential rotation procedure.
Kubernetes Secret storage does not by itself guarantee encryption at rest.

## Bootstrap the Argo CD project

Before the certificate-infrastructure Application is synchronized:

```bash
kubectl apply -f gitops/projects/platform-certificates.yaml
```

The project permits cluster-scoped ClusterIssuer resources only.
The Application is discovered through the existing homelab-apps root
Application after its manifest is merged into main.

## Staging issuer

The letsencrypt-staging ClusterIssuer uses ACME DNS-01 with Cloudflare.
Its manifests reference the credential Secret without containing its value.

cert-manager generates the ACME account key in the
letsencrypt-staging-account-key Secret in the cert-manager namespace.

The DNS solver selects ahaouari.com and its subdomains. This selection
does not restrict which Kubernetes users may request certificates.

Staging certificates are for testing and are not trusted by browsers.
No production issuer or HTTPS listener is introduced by this bootstrap.

## Validation and limits

Validated before introducing the issuer:

- All three cert-manager Deployments became ready.
- A valid Issuer passed server-side dry-run admission.
- The webhook rejected a Certificate whose renewBefore exceeded duration.
- GitOps schema validation and validator rejection tests passed.

A Ready ClusterIssuer does not prove that Cloudflare DNS permissions work.
An actual staging certificate request is required to validate DNS-01 issuance.

Certificate issuance, renewal, and browser HTTPS access remain to be tested.
The chart is version-pinned; container images currently use version tags.
