# Proxmox provisioning and bootstrap

This document records the Proxmox provisioning workflow, its validation,
and the permission changes made during implementation.

## Terraform configuration

| Component       | Configuration               |
| --------------- | --------------------------- |
| Terraform CLI   | 1.17.0, Linux AMD64         |
| Provider        | bpg/proxmox 0.117.0         |
| Proxmox node    | pve                         |
| API endpoint    | https://192.168.0.199:8006/ |
| VM disk storage | local-zfs                   |
| State backend   | Local                       |

The provider version is pinned and `.terraform.lock.hcl` is tracked in Git.
Terraform state, saved plans, and the `.terraform/` directory are excluded.

The current configuration manages four Kubernetes VMs. OPNsense and the
legacy Ubuntu template are not managed by this Terraform state.

## API authentication and TLS

Terraform uses the `terraform@pve!homelab-v2` API token with privilege
separation enabled.

The token was created with a 30-day expiration. Its exact expiry date is
not recorded here and must be checked before reuse.

The secret is supplied through `PROXMOX_VE_API_TOKEN`, not stored in HCL.
The local Proxmox CA certificate is supplied through `SSL_CERT_FILE`.
TLS verification remains enabled with `insecure = false`.

The CA certificate is stored locally at `private/pve-root-ca.pem`.
Its SHA-256 fingerprint was compared with the certificate on the Proxmox
host. An HTTPS request using that CA returned HTTP 200.

## Current permission model

The following permissions were granted to both the Terraform account
and its privilege-separated token.

| Path                               | Role                  | Privileges                               | Propagation |
| ---------------------------------- | --------------------- | ---------------------------------------- | ----------- |
| `/vms`                             | PVEVMAdmin            | Built-in VM administration role          | Yes         |
| `/nodes/pve`                       | TerraformNodeRead     | Sys.Audit                                | No          |
| `/storage/local`                   | TerraformImageRead    | Datastore.Audit                          | No          |
| `/storage/local-zfs`               | TerraformDiskAllocate | Datastore.Audit, Datastore.AllocateSpace | No          |
| `/sdn/zones/localnetwork/vmbr1`    | TerraformNetworkUse   | SDN.Use                                  | No          |
| `/sdn/zones/localnetwork/vmbr1/20` | TerraformNetworkUse   | SDN.Use                                  | No          |

This deliberately broad VM permission scope simplifies provisioning and
reconstruction in the personal lab. It includes the ability to administer
OPNsense and is not a least-privilege boundary.

### Historical permission test

During the initial API connectivity test, the account and token had only
node-read permissions. Reading the OPNsense VM configuration returned
HTTP 403 because `VM.Audit` was missing.

That result applies only to the initial permission model. It does not
describe the current permissions.

### Why the VM permission scope changed

The initial disposable VM used permissions assigned directly to its VM ID.
Destroying that VM also removed those ACL entries, so Terraform could not
recreate it with the same permissions.

The workflow was changed to inherit `PVEVMAdmin` from `/vms`. Disabling
purge during destruction was not a solution to this ACL removal behavior.

The VLAN 20 network path also required an explicit `SDN.Use` assignment:
the non-propagating permission on `vmbr1` did not cover its `/20` path.

## Ubuntu image preparation

The VMs use the official Ubuntu Server 24.04 LTS AMD64 cloud image,
build `20261017`.

Source:
https://cloud-images.ubuntu.com/releases/noble/release-20261017/

Image preparation was performed administratively on Proxmox before
Terraform provisioning.

Observed integrity checks:

- The signed checksum manifest passed GPG signature verification.
- The signing-key fingerprint matched
  `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`.
- The image passed SHA-256 verification against that manifest.
- The imported copy matched the downloaded image.
- `qemu-img info` identified the image as qcow2 and reported
  `corrupt: false`.

The source file had an `.img` extension. The import copy was renamed
`.qcow2` after its actual format was verified, allowing Proxmox to list it
as an importable image.

Terraform uses this storage identifier:

`local:import/ubuntu-24.04-server-cloudimg-amd64-20261017.qcow2`

The legacy template, VM 9000, was preserved and is not used by this workflow.

## Disposable VM validation

VM 110, `bootstrap-test`, was created before provisioning the cluster.

Observed checks included:

- SSH access as `ubuntu` using the dedicated administration key.
- Static address `10.10.20.110/24`, with gateway `10.10.20.1`.
- DNS resolution through `10.10.20.1`.
- An outbound IPv4 HTTPS request returning HTTP 200.
- An active NTP service and synchronized clock.
- QEMU Guest Agent communication through the Proxmox interface.
- Guest Agent operation after a reboot.
- Successful VM reconstruction.
- An Ansible rerun with no changes.
- A Terraform plan with no changes after the corrected reconstruction.

The disposable VM was subsequently removed through Terraform. Its
configuration file is no longer part of the desired infrastructure.

These results describe the disposable VM. They should not be treated as
independent proof that every check was repeated on every cluster node.

## Kubernetes VM provisioning

| VM           |  ID | Static address | vCPU |   RAM | System disk |
| ------------ | --: | -------------- | ---: | ----: | ----------: |
| k8s-cp01     | 201 | 10.10.20.11/24 |    2 | 4 GiB |      60 GiB |
| k8s-worker01 | 202 | 10.10.20.21/24 |    2 | 8 GiB |      80 GiB |
| k8s-worker02 | 203 | 10.10.20.22/24 |    2 | 8 GiB |      80 GiB |
| k8s-worker03 | 204 | 10.10.20.23/24 |    2 | 8 GiB |      80 GiB |

Each VM uses:

- A disk imported from the verified Ubuntu cloud image.
- A VirtIO network interface on `vmbr1`, tagged with VLAN 20 by Proxmox.
- Static addressing and DNS configuration through cloud-init.
- The `ubuntu` account with the dedicated SSH public key.
- QEMU Guest Agent support enabled in its virtual hardware.

SSH access and Ansible connectivity succeeded on all four nodes.
The Guest Agent playbook completed with no changes on a subsequent run.

### Recovery from partial provisioning

The three workers were created successfully during the initial cluster
apply. Control-plane creation failed and left an orphaned cloud-init
volume.

The recovery targeted the orphaned volume after checking for a VM
configuration and references. A new Terraform plan preserved the existing
workers and proposed only the missing control-plane VM.

The subsequent apply, using `-parallelism=1`, completed with one resource
added and no resources changed or destroyed.

Saved plans from earlier provisioning attempts must not be reused.

## Known cloud-init warning

Cloud-init reported `degraded done` with no blocking errors on the
disposable VM and the three workers.

The warning concerns the deprecated string form of `user`, with removal
announced for cloud-init 27.2. Inspection of the Proxmox-generated user
data identified `user: ubuntu`.

The warning remains unresolved. Custom cloud-init snippets have not been
introduced solely to suppress it. The full cloud-init status of the
control-plane VM was not recorded separately.

## Operating limits

- Terraform state is local; an off-host state backup strategy is pending.
- The API token can administer all VMs through its inherited permissions.
- A successful plan does not prove that every future apply has sufficient
  permissions.
- Recreating VM resources does not restore Kubernetes or application data.
- Full cluster reconstruction and off-host restoration remain untested.
