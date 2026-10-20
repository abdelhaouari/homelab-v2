# Architecture

The lab runs on a single Proxmox VE server. OPNsense provides routing between the internal network zones and the upstream network. The Kubernetes rebuild starts with one disposable Ubuntu VM to establish the provisioning and configuration workflow before creating the cluster nodes.

## Existing infrastructure

| Component | Configuration |
|---|---|
| Hypervisor | Proxmox VE 9.1.6 |
| Processor | Intel Xeon E5-1650 v3, 12 logical CPUs |
| Memory | 64 GB installed, approximately 62.70 GiB reported by Proxmox |
| Storage | ZFS RAIDZ1 pool across three SSDs |
| Firewall and router | OPNsense 26.1.7_3 |
| Network zones | Management, Kubernetes, storage, lab, and WireGuard |

These versions describe the infrastructure recorded on 2026-10-17. The legacy Ubuntu template is still present, but its contents have not been validated for the rebuild.

## Kubernetes sizing

The initial cluster target is one control plane and three workers.

| VM | Count | vCPU per VM | Memory per VM | Disk per VM |
|---|---:|---:|---:|---:|
| OPNsense, existing | 1 | 4 | 4 GiB | 32 GiB |
| Control plane | 1 | 2 | 4 GiB | 60 GiB |
| Worker | 3 | 2 | 8 GiB | 80 GiB |

Kubernetes accounts for 28 GiB of memory. Including OPNsense, the VM budget totals 32 GiB of memory, 12 vCPU, and 332 GiB of virtual disk capacity.

An initial allowance of 12 to 16 GiB for Proxmox and ZFS leaves approximately 15 to 19 GiB of memory headroom. Allocations will be adjusted using actual memory pressure, CPU utilization, and storage usage. The allowance does not set an ARC limit.

Three workers provide room to practice draining and rebuilding individual nodes while retaining capacity on the others. Application availability during maintenance depends on replica placement, resource requirements, disruption budgets, and storage behavior.

Virtual CPUs share the physical processor. Virtual disk allocations also differ from physical ZFS usage; snapshots, data, and backups consume additional space. Storage entries backed by the same ZFS pool share its physical capacity.

## Network layout

The existing Kubernetes network uses VLAN 20. Each Kubernetes VM will have one interface attached to `vmbr1`, with VLAN tag 20 applied by Proxmox. Ubuntu will use an untagged guest interface for this access-port configuration.

Proxmox administration remains on the upstream home network. Node addresses will be allocated after checking DHCP scopes, reservations, and existing assignments. Pod, Service, and LoadBalancer ranges must avoid overlap with the local networks, WSL, WireGuard, and any future cloud network.

OPNsense filters traffic that passes through it. Traffic between guests on the same VLAN may stay on the virtual bridge, so workload isolation also needs controls at the relevant host or Kubernetes boundary. Required and denied paths will be verified before introducing offensive exercises or intentionally vulnerable workloads.

## Provisioning workflow

| Tool | Responsibility |
|---|---|
| Terraform | VM lifecycle and virtual hardware |
| cloud-init | Initial guest identity, network configuration, and SSH access |
| Ansible | Operating system, container runtime, and Kubernetes configuration |

The initial design uses an official Ubuntu Server 24.04 LTS cloud image. Using a fresh image avoids inheriting unreviewed credentials and configuration from the previous template. Its exact source and digest will be recorded, and its signed checksum manifest verified before use.

Packer can be introduced if image customization becomes substantial enough to justify a separate build workflow. At this stage, the priority is a small provisioning path that can be inspected and repeated.

The first VM will be used to verify boot, addressing, SSH access, DNS resolution, and Ansible configuration. A second Ansible run will be reviewed for expected idempotence. Recreating that VM without its previous disk will then exercise the reconstruction path before expanding to the cluster.

## Operating limits

- The physical server and single control plane are points of failure.
- Node-local storage does not provide data availability after loss of its node.
- A backup on the same server does not protect against loss of the server.
- Network isolation and restoration procedures require testing before their effectiveness can be claimed.

## References

- [Ubuntu release cycle](https://ubuntu.com/about/release-cycle)
- [Creating a cluster with kubeadm](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)
