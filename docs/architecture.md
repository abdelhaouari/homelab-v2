# Architecture

## Purpose and current state

This homelab provides a practical foundation for infrastructure automation,
Kubernetes operations, application delivery, and platform security.

The current deployment consists of one control plane and three workers
running on Proxmox VE. Terraform provisions the VMs, cloud-init establishes
guest access and addressing, and Ansible configures the hosts and
Kubernetes packages.

All four nodes have reported Ready. Cilium and CoreDNS are operational.
A functional smoke test verified internal DNS, direct cross-node pod
communication, and HTTP access through a Kubernetes Service.

Application delivery pipelines and workload security controls are the next
phase. They are not yet implemented.

## Physical infrastructure

| Component           | Configuration                           |
| ------------------- | --------------------------------------- |
| Hypervisor          | Proxmox VE 9.1.6                        |
| Processor           | Intel Xeon E5-1650 v3, 12 logical CPUs  |
| Memory              | 64 GB installed                         |
| Storage             | ZFS RAIDZ1 pool across three SSDs       |
| Router and firewall | OPNsense VM, version observed: 26.1.7_3 |
| Kubernetes guests   | Ubuntu Server 24.04.5 LTS               |

All VMs share the same physical server and storage pool. The design does
not provide physical redundancy.

The legacy Ubuntu template, VM 9000, is preserved but is not used to
provision the new cluster.

## VM allocation

| VM           |  ID | Role                     | vCPU |   RAM | System disk |
| ------------ | --: | ------------------------ | ---: | ----: | ----------: |
| opnsense     | 100 | Router and firewall      |    4 | 4 GiB |      32 GiB |
| k8s-cp01     | 201 | Kubernetes control plane |    2 | 4 GiB |      60 GiB |
| k8s-worker01 | 202 | Kubernetes worker        |    2 | 8 GiB |      80 GiB |
| k8s-worker02 | 203 | Kubernetes worker        |    2 | 8 GiB |      80 GiB |
| k8s-worker03 | 204 | Kubernetes worker        |    2 | 8 GiB |      80 GiB |

The Kubernetes VMs have 28 GiB of allocated memory. Including OPNsense,
the allocation totals 32 GiB of memory, 12 vCPU, and 332 GiB of virtual
disk capacity.

An initial allowance of 12 to 16 GiB is reserved in the capacity plan for
Proxmox and ZFS. This is a planning allowance, not a configured ARC limit.

Virtual CPUs share the physical processor. Virtual disk sizes do not
represent current physical consumption. Proxmox storage entries backed by
the same ZFS pool share its capacity.

Three workers provide a basis for testing replica placement and node
maintenance. Application availability during those operations has not yet
been demonstrated.

## Network architecture

### Infrastructure networks

| Network      | Range          | Purpose                                          |
| ------------ | -------------- | ------------------------------------------------ |
| Home network | 192.168.0.0/24 | Upstream connectivity and Proxmox administration |
| VLAN 10      | 10.10.10.0/24  | Management                                       |
| VLAN 20      | 10.10.20.0/24  | Kubernetes nodes                                 |
| VLAN 30      | 10.10.30.0/24  | Storage network zone                             |
| VLAN 40      | 10.10.40.0/24  | Lab network zone                                 |
| WireGuard    | 10.10.50.0/24  | VPN network                                      |

These network zones describe the existing layout. Their presence does not
prove that isolation policies have been enforced or tested.

Proxmox administration uses `192.168.0.199` on `vmbr0`.
The OPNsense WAN address is `192.168.0.210`.

Each Kubernetes VM has one VirtIO interface connected to `vmbr1`.
Proxmox applies VLAN tag 20; Ubuntu uses an untagged guest interface.

### Node addressing

| Node         | Address        | Gateway and DNS |
| ------------ | -------------- | --------------- |
| k8s-cp01     | 10.10.20.11/24 | 10.10.20.1      |
| k8s-worker01 | 10.10.20.21/24 | 10.10.20.1      |
| k8s-worker02 | 10.10.20.22/24 | 10.10.20.1      |
| k8s-worker03 | 10.10.20.23/24 | 10.10.20.1      |

Cloud-init configures these static addresses from Terraform.

The OPNsense DHCP pool is `10.10.20.200` through `10.10.20.250`.
The node addresses are outside that pool and do not require DHCP
reservations to prevent dynamic allocation.

### Kubernetes networks

| Network            | Range         | Management                               |
| ------------------ | ------------- | ---------------------------------------- |
| Pods               | 10.244.0.0/16 | Kubernetes allocates per-node CIDRs      |
| Services           | 10.96.0.0/16  | Kubernetes allocates virtual Service IPs |
| Cluster DNS domain | cluster.local | CoreDNS                                  |

The selected ranges do not overlap the documented infrastructure networks
or the WSL and node routes inspected during deployment. Routes introduced
by future VPN or cloud connections must be checked separately.

Observed PodCIDR assignments:

| Node         | PodCIDR       |
| ------------ | ------------- |
| k8s-cp01     | 10.244.0.0/24 |
| k8s-worker01 | 10.244.2.0/24 |
| k8s-worker02 | 10.244.1.0/24 |
| k8s-worker03 | 10.244.3.0/24 |

These assignments are observations from this deployment. A rebuild may
allocate the per-node ranges in a different order.

## Kubernetes and runtime configuration

| Component               | Configuration                              |
| ----------------------- | ------------------------------------------ |
| Kubernetes              | v1.36.5                                    |
| Kubernetes APT packages | 1.36.5-1.1, held against ordinary upgrades |
| Bootstrap tool          | kubeadm                                    |
| Container runtime       | containerd 2.2.1                           |
| Runtime socket          | unix:///run/containerd/containerd.sock     |
| Cgroup driver           | systemd                                    |
| Swap                    | Disabled                                   |
| IPv4 forwarding         | Enabled                                    |
| API endpoint            | 10.10.20.11:6443                           |

The control plane runs etcd, kube-apiserver, kube-controller-manager, and
kube-scheduler as static pods managed by the kubelet.

The API endpoint points directly to the single control-plane VM.
There is no API load balancer or redundant control plane.

Worker joining uses short-lived bootstrap tokens generated on the control
plane. Sensitive command output is suppressed in Ansible. The playbook
checks for existing kubelet configuration before attempting a join and
verifies node registration through the API.

Registration alone does not prove node health. Readiness and workload
connectivity are checked separately.

## Cilium networking

Cilium 1.20.4 is installed through Helm with configuration stored in
`kubernetes/cilium/values.yml`.

| Setting                | Choice              |
| ---------------------- | ------------------- |
| Routing mode           | Tunnel              |
| Tunnel protocol        | VXLAN               |
| IP address management  | Kubernetes PodCIDRs |
| kube-proxy replacement | Disabled            |
| Address family         | IPv4                |
| Operator replicas      | 2                   |

Each Cilium agent allocates pod addresses from its node's Kubernetes
PodCIDR. VXLAN encapsulates inter-node pod traffic using the VM network,
avoiding the need for pod-subnet routes in OPNsense.

VXLAN does not encrypt traffic. Workload encryption has not been configured.

kube-proxy remains deployed for Service networking. Cilium NetworkPolicy
enforcement has not yet been exercised through allow and deny tests.

OPNsense filters traffic that traverses the router. Traffic between VMs
on VLAN 20 can remain on the Proxmox bridge. Workload isolation therefore
requires controls at the Kubernetes or host boundary as appropriate.

Both CoreDNS replicas were observed on the same worker during initial
validation. DNS availability after losing that worker has not been tested.

## Automation boundaries

| Tool | Responsibility |
|---|---|
| Terraform | VM lifecycle, virtual hardware, and cloud-init inputs |
| cloud-init | Initial guest user, SSH key, and network configuration |
| Ansible | Host preparation, cluster bootstrap checks, worker joining, local access, and Cilium orchestration |
| kubeadm | Control-plane initialization and node joining |
| Helm | Cilium release management, invoked through Ansible |
| kubectl | Readiness checks and functional tests |

The official Ubuntu cloud image was verified against its signed checksum
manifest before import. Image preparation and Proxmox API permissions
remain administrative prerequisites.

The consolidated entry point, `ansible/site.yml`, executes:

1. Guest Agent configuration.
2. Operating system preparation.
3. containerd configuration.
4. Kubernetes package installation.
5. Control-plane initialization or verification.
6. Worker joining or registration verification.
7. Local administrator kubeconfig retrieval.
8. Cilium release management and readiness checks.

Local dependencies include the versioned Ansible collection requirements
and the helm-diff plugin. The rebuild procedure documents their setup.

The complete Ansible workflow was rerun against the existing cluster
with zero changes and no failures on all four nodes and localhost.
Package index refreshes remain time-dependent.

Control-plane initialization checks require either no detected markers
or the expected set of existing markers. Inconsistent state stops the
workflow. Existing control planes must also pass an API readiness check.

Worker joining checks local kubelet configuration and API registration.
These safeguards do not constitute automatic recovery from every partial
failure. No automatic cluster reset is performed.

Hubble TLS certificates use Cilium's CronJob generation method. This
avoids the changing certificate content produced by Helm-based generation
during repeated renders. The initial certificate Job completed, and a
subsequent Ansible run reported no changes. Scheduled renewal remains
untested.

The consolidated workflow has not yet been validated through a complete
rebuild from fresh VMs. It does not implement Kubernetes upgrades or
application data restoration.

See `rebuild.md` for prerequisites, commands, and functional validation.

## Validation evidence

| Layer                 | Observed result                                                |
| --------------------- | -------------------------------------------------------------- |
| Provisioning          | Four Kubernetes VMs created through Terraform                  |
| Administration        | SSH and Ansible access succeeded on all four VMs               |
| Runtime               | containerd CRI plugins reported healthy                        |
| Host settings         | No active swap; IPv4 forwarding enabled                        |
| Packages              | kubeadm, kubelet, and kubectl installed at 1.36.5-1.1 and held |
| Cluster               | All four nodes reported Ready                                  |
| Networking components | Cilium agents, operators, and CoreDNS reported ready           |
| DNS                   | Test Service resolved to its ClusterIP                         |
| Cross-node traffic    | Direct pod HTTP request returned the expected response         |
| Service traffic       | HTTP through the Service name returned the expected response   |

The smoke test in `kubernetes/tests/network-smoke.yml` places a server on
`k8s-worker01` and a client on `k8s-worker02`.

Both HTTP paths returned `homelab-network-ok`. This is a targeted
functional test, not an exhaustive test of every node pair, protocol,
packet size, or failure scenario.

The scheduler and controller-manager each showed one restart during
initial deployment. Both were subsequently observed Ready; the cause of
those restarts has not been established.

## Security and operating limits

- All nodes depend on one physical server and one storage pool.
- The single control plane is a point of failure.
- Terraform has broad VM administration permissions, including OPNsense.
- The local administrator kubeconfig grants privileged cluster access.
- Secrets, kubeconfigs, Terraform state, and plans are excluded from Git.
- Terraform state is local; off-host state protection remains pending.
- Strict network segmentation and workload policy enforcement are unverified.
- Node-local data does not survive loss of the underlying storage.
- Off-host backup and restore procedures have not been validated.
- Recreating infrastructure does not restore application data.

A Proxmox-generated cloud-init deprecation warning remains documented in
`proxmox-bootstrap.md`.

## Next architecture milestones

1. Test the consolidated deployment workflow through a complete rebuild.
2. Deploy an application with explicit authentication and authorization.
3. Add CI/CD security checks with demonstrated failure and remediation.
4. Validate workload isolation and pipeline identity controls.
5. Implement off-host backups and test restoration.

Tool selection for later stages will follow concrete application and
operating requirements.
