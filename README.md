# Homelab V2 | Kubernetes & Platform Security

A four-node Kubernetes homelab built on Proxmox VE, with Terraform provisioning, Ansible host configuration, and Cilium networking.

This project develops practical skills in infrastructure automation, Kubernetes operations, and platform security. The implemented foundation supports the next phase: deploying an application and demonstrating security controls throughout its delivery pipeline.

**Current milestone:** the four-node Kubernetes foundation is operational
and its networking has been validated. A local FastAPI application now
supports authenticated image promotion requests, role-based decisions,
and PostgreSQL persistence. Application containerization and CI/CD are
the next delivery milestones.

## What has been built

- **Infrastructure as code:** Terraform provisions four Ubuntu VMs, including CPU, memory, disks, VLAN attachment, static addressing, and cloud-init SSH configuration.
- **Repeatable host configuration:** Ansible installs the QEMU Guest Agent, configures containerd with systemd cgroups, prepares host networking, and installs version-pinned Kubernetes packages.
- **Kubernetes lifecycle operations:** kubeadm initializes the control plane; an Ansible playbook joins workers using short-lived bootstrap tokens without displaying their values.
- **Cluster networking:** Cilium provides a VXLAN overlay using Kubernetes-assigned PodCIDRs, with kube-proxy retained for Service networking.
- **Functional verification:** a reusable smoke test checks DNS, direct HTTP between pods on different workers, and HTTP through a ClusterIP Service.
- **Application security:** a FastAPI promotion API integrates Keycloak,
  OIDC authentication, access token validation, and role-based authorization.
- **Data integrity:** PostgreSQL constraints, restricted database permissions,
  and conditional updates protect request records and prevent competing
  decisions from overwriting each other.
- **Security validation:** automated tests cover business rules, token
  validation, HTTP authorization, persistence, and concurrent decisions.
  Manual checks exercise real Keycloak login, PKCE rejection, and
  authenticated API operations.

## Artifact promotion application

The application records requests to promote a container image digest
to staging. Developers submit requests, approvers approve or reject
them, and readers inspect the results. Requesters cannot approve or
reject their own requests.

A local CLI authenticates users through Keycloak using Authorization
Code with PKCE S256. The API validates access tokens and derives user
identities and permissions from verified claims.

FastAPI currently runs in WSL, while PostgreSQL and Keycloak run in
local Docker Compose containers. A versioned realm configuration was
successfully imported into a fresh, disposable Keycloak instance.

The application records approval decisions; it does not deploy images
or verify their signatures, provenance, or scan results. Application
deployment to Kubernetes and delivery-pipeline controls remain planned.

See [application documentation](docs/application.md) for endpoints,
authorization rules, validation evidence, and local configuration.

## Architecture

The cluster runs on a single physical Proxmox server with 64 GB of RAM and a ZFS RAIDZ1 pool. OPNsense provides the gateway for the Kubernetes VLAN.

| Node           | Role          | vCPU |   RAM | System disk | Address       |
| -------------- | ------------- | ---: | ----: | ----------: | ------------- |
| `k8s-cp01`     | Control plane |    2 | 4 GiB |      60 GiB | `10.10.20.11` |
| `k8s-worker01` | Worker        |    2 | 8 GiB |      80 GiB | `10.10.20.21` |
| `k8s-worker02` | Worker        |    2 | 8 GiB |      80 GiB | `10.10.20.22` |
| `k8s-worker03` | Worker        |    2 | 8 GiB |      80 GiB | `10.10.20.23` |

### Network design

| Network                   | Range                       | Allocation                                                    |
| ------------------------- | --------------------------- | ------------------------------------------------------------- |
| Kubernetes nodes, VLAN 20 | `10.10.20.0/24`             | Static addresses through cloud-init                           |
| DHCP pool on VLAN 20      | `10.10.20.200–10.10.20.250` | OPNsense DHCP                                                 |
| Pods                      | `10.244.0.0/16`             | Kubernetes assigns a `/24` per node; Cilium allocates pod IPs |
| Services                  | `10.96.0.0/16`              | Kubernetes ClusterIP allocation                               |

Node addresses are outside the DHCP pool. Pod and Service ranges were checked against the documented lab networks and the observed WSL and node routes.

VXLAN carries inter-node pod traffic over the VM network without requiring pod-subnet routes in OPNsense. VXLAN encapsulation does not encrypt traffic.

### Validated software baseline

| Component                  | Version               |
| -------------------------- | --------------------- |
| Ubuntu Server              | 24.04.5 LTS           |
| Kubernetes                 | 1.36.5                |
| containerd                 | 2.2.1                 |
| Cilium                     | 1.20.4                |
| Terraform                  | 1.17.0                |
| Proxmox Terraform provider | `bpg/proxmox` 0.117.0 |
| Ansible Core               | 2.21.5                |

Kubernetes packages use the exact APT version `1.36.5-1.1` and are held to prevent unplanned upgrades. The Cilium chart version is specified explicitly during installation.

## Engineering decisions

### Separate provisioning from configuration

Terraform owns VM resources and their lifecycle. Cloud-init establishes initial network and SSH access. Ansible configures the operating system and Kubernetes components. Helm installs Cilium from a versioned values file.

This separation keeps infrastructure changes distinct from guest configuration and cluster add-ons.

### Validate the provisioning path before scaling it

A disposable VM was used to verify cloud-init, SSH access, DNS, outbound HTTPS, time synchronization, and the QEMU Guest Agent.

That VM was also recreated to exercise the provisioning path, then removed through Terraform before completing the four-node cluster.

### Make configuration repeatable

Repeated Ansible runs confirmed no further changes for the Guest Agent, containerd, and host preparation. Worker joining skips nodes with existing kubelet configuration and checks their registration through the Kubernetes API.

Package index refreshes remain time-dependent. An existing kubelet configuration is not treated as sufficient evidence of a healthy node.

## Security considerations

Implemented measures include:

- Verification of the Ubuntu cloud image against its signed checksum manifest.
- Proxmox API TLS verification using the local certificate authority.
- API credentials supplied through an environment variable rather than Terraform files.
- A dedicated SSH key for lab administration.
- Short-lived worker bootstrap tokens, with sensitive Ansible output suppressed.
- A dedicated local administrator kubeconfig with restricted file permissions.
- Git exclusions for credentials, private keys, kubeconfigs, Terraform state, plans, and local environments.

The Proxmox token intentionally has VM administration permissions across `/vms` to simplify this personal lab. This includes access to the OPNsense VM and is not a least-privilege boundary.

Network segmentation and Kubernetes NetworkPolicy enforcement have not yet been validated. Traffic between VMs on the same VLAN can remain on the Proxmox bridge without passing through OPNsense.

## Validation

The following results were observed during deployment:

| Check                     | Result                                                               |
| ------------------------- | -------------------------------------------------------------------- |
| Kubernetes node readiness | All four nodes reported `Ready`                                      |
| Cilium agents             | Ready on all four nodes                                              |
| Cilium operators          | Two replicas ready                                                   |
| CoreDNS                   | Both replicas ready                                                  |
| Internal DNS              | Test Service resolved to its ClusterIP                               |
| Cross-node pod traffic    | HTTP request returned the expected response                          |
| Service networking        | HTTP request through the Service name returned the expected response |

The network smoke test places a server on `k8s-worker01` and a client on `k8s-worker02`. Both direct pod access and Service access returned:

```text
homelab-network-ok
```

These checks establish basic cluster connectivity. They do not establish network isolation, performance, recovery capability, or application availability during failure.

## Repository structure

```text
.
├── ansible/
│   ├── bootstrap.yml
│   ├── cilium.yml
│   ├── containerd.yml
│   ├── files/
│   │   └── kubeadm-init.yml
│   ├── init-control-plane.yml
│   ├── inventory.yml
│   ├── join-workers.yml
│   ├── kubernetes.yml
│   ├── local-access.yml
│   ├── prepare-hosts.yml
│   ├── requirements.txt
│   ├── requirements.yml
│   └── site.yml
├── app/
│   ├── keycloak/
│   ├── scripts/
│   ├── sql/
│   ├── src/promotion_api/
│   ├── tests/
│   ├── compose.yml
│   ├── requirements.txt
│   ├── requirements-cli.txt
│   └── requirements-dev.txt
├── docs/
│   ├── application.md
│   ├── architecture.md
│   ├── proxmox-bootstrap.md
│   └── rebuild.md
├── kubernetes/
│   ├── cilium/
│   │   └── values.yml
│   └── tests/
│       └── network-smoke.yml
└── terraform/
    ├── .terraform.lock.hcl
    ├── cluster-vms.tf
    ├── connection-check.tf
    ├── providers.tf
    └── versions.tf
```

## Provisioning and rebuild workflow

The consolidated Ansible entry point configures the hosts, initializes
or verifies the control plane, joins or verifies workers, retrieves the
local kubeconfig, and manages Cilium.

After provisioning the VMs with Terraform and preparing the local
dependencies, run:

```bash
.venv/bin/ansible-playbook \
  -i ansible/inventory.yml \
  ansible/site.yml
```

The complete Ansible workflow was rerun against the existing deployment
with zero changes and no failures across all four nodes and localhost.

Control-plane initialization checks reject inconsistent local state
instead of automatically resetting the cluster. Hubble certificates are
generated and renewed through Cilium's CronJob mechanism, avoiding
certificate changes on every Helm render.

See the [provisioning and rebuild procedure](docs/rebuild.md) for
prerequisites, execution order, state handling, and functional tests.

A complete rebuild from fresh VMs has not yet been tested with this
consolidated workflow. Scheduled certificate renewal and off-host
restoration also remain unverified.

All nodes share one physical server, and the cluster has one control
plane. The environment is not highly available.

Terraform state is stored locally and excluded from Git. Recreating
infrastructure does not recover application data.

## Next milestones

1. Containerize the promotion API and validate its runtime configuration.
2. Automate tests, secret scanning, SAST, and dependency scanning in CI.
3. Build and publish the application image, then introduce image signing
   and verification.
4. Deploy the application to Kubernetes and validate access, configuration,
   and health probes.
5. Demonstrate a failing security control, remediation, and successful delivery.
6. Validate infrastructure rebuilds, data recovery, and workload isolation.

These are planned extensions, not completed capabilities.
