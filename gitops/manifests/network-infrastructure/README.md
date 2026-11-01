# LAN gateway network infrastructure

This directory defines the address allocation and L2 announcement policy
for the shared homelab Gateway.

## Configuration

- Gateway address: `10.10.20.103`.
- VLAN subnet: `10.10.20.0/24`.
- DHCP pool: `10.10.20.200` through `10.10.20.250`.
- Eligible Services carry `networking.ahaouari.com/exposure: lan-gateway`.
- Worker nodes announce LoadBalancer addresses on `eth0`.
- Control-plane nodes are excluded from announcement eligibility.
- Service externalIPs are not announced by this policy.

The pool contains one address. Multiple applications will share it through
the same Gateway and hostname-based routes.

LB IPAM allocates the address. L2 announcements make it reachable on the
local network. Neither resource creates a Gateway, HTTP route, certificate,
DNS record, or firewall rule.

## Ownership and bootstrap

The `network-infrastructure` Argo CD Application manages these resources
through the `platform-network` AppProject.

Bootstrap the project before synchronizing the Application:

```bash
kubectl apply -f gitops/projects/platform-network.yaml
```

The project permits only `CiliumLoadBalancerIPPool` and
`CiliumL2AnnouncementPolicy` cluster resources.

Automatic synchronization and self-healing are enabled. Pruning is disabled.

Cilium itself remains managed by the Ansible Helm playbook. Gateway API CRDs
are installed separately with:

```bash
bash kubernetes/gateway-api/install-crds.sh
```

Install those CRDs before enabling Gateway API in Cilium on a fresh cluster.

## Operational limits

L2 announcements are marked Beta in Cilium 1.20.4. One elected node announces
each selected Service address. Failover is not instantaneous.

Clients on another subnet require routing and firewall access to VLAN 20.
The Service selector is an allocation and announcement filter, not an
authorization boundary.

Use externalTrafficPolicy: Cluster for the Gateway LoadBalancer Service.
Cilium L2 announcements do not support externalTrafficPolicy: Local.

LAN reachability was validated through the deployed shared Gateway:
the Argo CD hostname resolved to `10.10.20.103` on the Windows workstation,
HTTP redirected to HTTPS, and verified HTTPS and browser login succeeded.
See [Argo CD routing](../argocd-routing/README.md).

Announcement failover and a complete fresh-cluster rebuild remain
unvalidated. Successful access through the current elected worker does
not establish failover behavior.
