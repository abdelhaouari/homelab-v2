# Private REx-PN practice site

URL: **https://rexpn.lab.ahaouari.com**.

The original standalone HTML is stored unchanged in `app/rexpn/index.html`.
Kustomize generates content and Nginx ConfigMaps with content hashes, so a
content/configuration change updates the Deployment's volume references and
triggers a rollout. At about 210 KB the HTML fits within the 1 MiB ConfigMap
limit. No custom image build, registry credentials, backend, or PVC is needed.

Two Nginx replicas use an upstream image pinned by digest, UID/GID 65532,
read-only root filesystems, dropped capabilities, no API token, resource
limits, HTTP probes and preferred distribution across nodes. Only `/tmp`
is writable. The digest was resolved from `cgr.dev/chainguard/nginx:latest` on
2026-11-22; review upstream image updates regularly. This namespace is not
covered by the existing promotion-specific Kyverno signature policy.

The Cilium policy permits TCP 8080 from the `ingress` identity and denies
outbound pod connections. Browser links to reference websites still work:
they originate on the user's device. Cilium's documented Gateway identity
is used rather than a namespace selector for Envoy:
https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/gateway-api/

## Verified deployment, 2026-11-22

Argo CD reports `rexpn` and `shared-gateway` Synced/Healthy; both site replicas
are ready. The production Certificate is Ready, and the HTTPS route reports
Accepted/ResolvedRefs. DNS resolves to `10.10.20.103`; HTTP redirects to HTTPS.
HTTPS returns 200 with certificate verification, and the served HTML is
byte-identical to the supplied original (SHA-256
`2ffc0fcfa92d2942df0e40529a31b2414902552a9a47582f4ad4fb7be48b5338`).
Argo CD HTTPS still returns 200. The private CI run 45048190181 passed its
server checks and HIGH/CRITICAL image scan. Mobile-data/VPN access must be
checked on the user's phone; it was not independently tested here.

## Delivery and bootstrap

The HTML, server configuration and workload manifests live in the private
`abdelhaouari/rexpn-site` repository. The public `homelab-v2` repository
contains only the Application, AppProject, namespace, Gateway and Certificate.
Argo CD uses a repository-specific read-only SSH deploy key, stored in an
Argo CD repository Secret provisioned outside Git. Never commit that key.

The Argo CD Application uses the dedicated `rexpn` AppProject. As with the
other applications, namespace/project bootstrap is explicit; workloads are
reconciled by Argo CD. Automated sync/self-heal and pruning are enabled for REx-PN.
`PruneLast=true` delays cleanup until the other sync resources are healthy.

From the `homelab-v2` repository root, bootstrap the namespace and project:

```bash
export KUBECONFIG="$PWD/private/homelab-v2.kubeconfig"
kubectl apply -f gitops/bootstrap/rexpn-namespace.yaml
kubectl apply -f gitops/projects/rexpn.yaml
```

Provision the private repository credential before synchronizing the app.
Push the private repository first, then the public infrastructure changes.
The root Application discovers `rexpn`; `shared-gateway` adds its certificate
and listener. Do not manually apply the workload bundle. Certificate issuance
and route readiness may lag behind the first sync.

Workload commands below run from the **private repository** checkout, using
an absolute `KUBECONFIG` path. The public repository's validator covers only
public infrastructure; the private repository CI validates and tests the site.

## Pi-hole and VPN

Add a **local DNS A record** in Pi-hole:

```text
rexpn.lab.ahaouari.com -> 10.10.20.103
```

The phone must use Pi-hole while on the LAN and while connected to the VPN.
The VPN must route `10.10.20.103` (or the cluster subnet `10.10.20.0/24`)
and the Pi-hole address. Permit VPN clients to reach Pi-hole on UDP/TCP 53
and the gateway on TCP 443 (80 is used only for HTTPS redirection).
Check that private DNS/DoH on the phone does not bypass Pi-hole.

No WAN port forwarding or public A/AAAA record is needed. The existing
Let's Encrypt issuer uses Cloudflare DNS-01; it does not require inbound
Internet access to this site. Public certificates disclose the hostname
through certificate transparency. The app has no login: every client that
can reach the gateway and hostname can use it. LAN/VPN firewall rules are
the access boundary; a private address alone does not enforce those rules.

## Verification

```bash
bash ci/scripts/validate-gitops.sh
bash ci/scripts/test-rexpn.sh  # Requires a working Docker daemon.

kubectl -n argocd get application rexpn shared-gateway
kubectl -n rexpn rollout status deployment/rexpn --timeout=120s
kubectl -n rexpn get pods,service,httproute,ciliumnetworkpolicy
kubectl -n ingress-system get certificate rexpn
kubectl -n ingress-system get gateway homelab-gateway
kubectl -n rexpn get httproute rexpn-https -o yaml

# Isolate gateway/TLS validation from local DNS. Do not use -k.
curl --fail --resolve rexpn.lab.ahaouari.com:443:10.10.20.103 \
  https://rexpn.lab.ahaouari.com/ -o /tmp/rexpn-served.html
cmp app/rexpn/index.html /tmp/rexpn-served.html
curl --head --resolve rexpn.lab.ahaouari.com:80:10.10.20.103 \
  http://rexpn.lab.ahaouari.com/
```

Expect Synced/Healthy Applications, ready replicas, a Ready Certificate,
Accepted/Programmed Gateway, Accepted/ResolvedRefs routes, HTTPS 200 and
HTTP 301 to HTTPS. Check Argo CD's existing HTTPS route still works.
Then check Pi-hole resolution and load the site on the phone over mobile
data with VPN enabled; test again with VPN disabled to confirm private
access. Practice a question, reload, and verify the saved progress.

## Progress, updates and rollback

Progress remains in each browser's localStorage. Hosting does not synchronize
phone and computer. Use **Carnet > Exporter ma progression**, then import on
the other device. File URLs, HTTP and HTTPS have separate storage; retain
the HTTPS hostname to preserve the same browser storage across updates.

Replace `app/rexpn/index.html` with the next complete HTML, validate and
commit. `Cache-Control: no-cache` makes subsequent loads revalidate without
clearing localStorage. Existing open tabs keep their loaded version until
reloaded. Revert the relevant Git change to roll back; no database restore
is involved. Argo CD automatically removes obsolete ConfigMaps after a
healthy sync. Roll back through Git so Kustomize recreates the required
ConfigMap; a direct Deployment rollback may reference a pruned ConfigMap.

The included LISEZ-MOI describes the author's educational limitations;
deployment checks do not independently validate medical content.
