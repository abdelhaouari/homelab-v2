# Argo CD LAN access

URL: https://argocd.lab.ahaouari.com

The local DNS record points to 10.10.20.103. The shared Cilium Gateway
terminates TLS using the production certificate in ingress-system.
HTTP requests for this hostname are redirected to HTTPS.

The HTTPS route forwards requests to argocd-server:80 in argocd.
Gateway-to-server traffic is HTTP and is not encrypted.
Argo CD authentication remains enabled.

## Ownership and deployment

Argo CD manages the routes and Gateway manifests.
Helm manages the Argo CD server configuration.

Before synchronizing this Application, bootstrap its project:

    kubectl apply -f gitops/projects/platform-argocd-routing.yaml

Apply the versioned Argo CD Helm values using chart 10.11.6.
The values set server.insecure=true and configure the external URL.
Changing the values file in Git alone does not update the Helm release.

The Gateway allows HTTPRoute attachments from the argocd namespace.
The route backend is in the same namespace, so no ReferenceGrant is needed.

## Scope

This configuration provides LAN access to the UI. It does not configure
public Internet exposure or native gRPC CLI routing.

## Verified behavior

- The production argocd Certificate reached Ready=True.
- Gateway listeners reported Accepted, ResolvedRefs, and Programmed.
- The HTTPS route reported Accepted and ResolvedRefs.
- Local DNS on the Windows workstation resolved the hostname to 10.10.20.103.
- HTTP returned a 301 redirect to HTTPS.
- HTTPS returned 200 without bypassing certificate verification.
- Browser login succeeded without a port-forward.
- All seven Argo CD Applications were Synced and Healthy.

TLS terminates at the Gateway. Gateway-to-Argo-CD traffic remains
unencrypted HTTP inside the cluster.

Automatic certificate renewal and Gateway failover have not yet been
validated. This result does not demonstrate public Internet accessibility.
