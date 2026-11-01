# Shared LAN Gateway

This directory defines the shared Cilium Gateway in `ingress-system`.
It now serves Argo CD on the LAN with HTTP-to-HTTPS redirection and a
production certificate for `argocd.lab.ahaouari.com`.

## Bootstrap

Create the namespace and Argo CD project before synchronizing the Application:

```bash
kubectl apply -f gitops/bootstrap/ingress-namespace.yaml
kubectl apply -f gitops/projects/platform-gateway.yaml
```

Prerequisites:

- Gateway API CRDs are installed.
- Cilium Gateway API and L2 announcements are enabled.
- The `network-infrastructure` Application has synchronized its IP pool
  and L2 announcement policy.
- cert-manager is installed, the Cloudflare credential Secret exists,
  and the certificate-infrastructure Application manages the ACME issuers.
- The `argocd-routing` Application manages the routes in `argocd`.

## Current configuration

The Gateway requests `10.10.20.103` and propagates the
`networking.ahaouari.com/exposure: lan-gateway` label to its generated
infrastructure.

| Listener | Port | Hostname | Behavior |
| --- | --- | --- | --- |
| `http` | 80 | Route selects the Argo CD hostname | HTTPRoute redirects to HTTPS with status 301 |
| `https-argocd` | 443 | `argocd.lab.ahaouari.com` | Terminates TLS using `argocd-tls`; HTTPRoute forwards to Argo CD |

Both listeners accept HTTPRoutes only from the namespace selected by
`kubernetes.io/metadata.name: argocd`. Routes reference this Gateway
across namespaces through `parentRefs`; the allowedRoutes selector
permits that attachment.

The production `argocd` Certificate writes `argocd-tls` in the Gateway's
namespace. The separate `argocd-staging` Certificate writes
`argocd-staging-tls`, which is not attached to a listener.

TLS ends at the Gateway. The HTTPS route forwards HTTP to
`argocd-server:80` in `argocd`, where the backend Service and route share
a namespace. No backend ReferenceGrant is required.

The `shared-gateway` Argo CD Application manages the Gateway and both
Certificate resources.
Cilium manages its generated Service and proxy configuration.
cert-manager manages issuance and the generated certificate Secrets.

Automatic synchronization and self-healing are enabled. Pruning is disabled.

## Validation

The October 31, 2026 review observed a Programmed Gateway at
`10.10.20.103` and both Certificates ready. Previously recorded tests
also verified listener and route conditions, LAN HTTP redirection,
HTTPS with certificate verification, and browser login.

After a configuration change, verify:

- The Gateway reports Accepted and Programmed.
- Its address is `10.10.20.103`.
- Its generated LoadBalancer Service carries the expected label.
- The Service uses externalTrafficPolicy: Cluster.
- A worker holds the corresponding Cilium L2 announcement lease.
- The production Certificate is ready and the listeners resolve its Secret.
- The Argo CD routes report Accepted and ResolvedRefs.
- Local DNS resolves the hostname to `10.10.20.103`.
- HTTP for the Argo CD hostname redirects to HTTPS.
- HTTPS succeeds with certificate verification and Argo CD login works.

An unmatched HTTP hostname can return 404; that alone does not validate
the configured Argo CD route. See [Argo CD access](../argocd-routing/README.md)
and [certificate bootstrap](../../../kubernetes/cert-manager/README.md).

## Scope and remaining work

Only Argo CD is currently routed. The promotion application and Keycloak
still use localhost port-forwards. Adding them requires listener/route
configuration and consistent application OIDC URLs.

Public Internet exposure, Gateway failover, and automatic certificate
renewal have not been validated. The single address can serve additional
hostnames through future listener and route configuration.
