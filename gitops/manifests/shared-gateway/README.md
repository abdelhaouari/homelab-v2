# Shared LAN Gateway

This directory defines the shared Cilium Gateway in `ingress-system`.

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

## Initial configuration

The Gateway requests `10.10.20.103` and propagates the
`networking.ahaouari.com/exposure: lan-gateway` label to its generated
infrastructure.

The HTTP listener uses port 80 and accepts routes only from its own
namespace. No application route or HTTPS listener is configured yet.

The `shared-gateway` Argo CD Application manages the Gateway.
Cilium manages its generated Service and proxy configuration.

Automatic synchronization and self-healing are enabled. Pruning is disabled.

## Validation

After synchronization, verify:

- The Gateway reports Accepted and Programmed.
- Its address is `10.10.20.103`.
- Its generated LoadBalancer Service carries the expected label.
- The Service uses externalTrafficPolicy: Cluster.
- A worker holds the corresponding Cilium L2 announcement lease.
- An HTTP request from the LAN reaches the Gateway.

With no matching HTTPRoute, an HTTP 404 response is expected. This validates
HTTP reachability only, not TLS or application routing.
