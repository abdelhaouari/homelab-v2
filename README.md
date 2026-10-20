# Homelab V2

A Kubernetes homelab focused on reproducible infrastructure, platform security, and application delivery.

This repository documents the rebuild of a personal lab running on Proxmox VE. The work covers VM provisioning, operating system configuration, Kubernetes administration, and security controls exercised through a small application.

Proxmox VE and OPNsense are already in place. The repository currently contains the architecture notes for the rebuild. Provisioning code and operating procedures will be added as the platform is implemented.

## Infrastructure

The initial design uses Ubuntu Server VMs with containerd and kubeadm. Terraform manages VM resources, cloud-init handles initial guest configuration, and Ansible configures the hosts and cluster.

The cluster target is one control plane and three workers, running on a single physical server with 64 GB of RAM. See the [architecture notes](docs/architecture.md) for the resource budget, network layout, and design rationale.

## Repository layout

```text
.
├── README.md
├── .gitignore
└── docs/
    └── architecture.md
```

Infrastructure code, configuration, and deployment instructions will be added alongside their implementation. Documentation will include the commands used, relevant results, and any operating limitations.

## Scope

This is a personal learning environment. All initial nodes share one physical host, so the cluster cannot remain available after loss of that host. Data recovery requires backups stored outside the server.

Configuration examples and application data are intended for public use. Credentials, private keys, privileged kubeconfigs, Terraform state, and backup archives remain outside this repository.
