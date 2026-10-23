# Provisioning and rebuild procedure

## Validation status

The consolidated Ansible entry point has been executed against the
existing cluster with zero changes and no failures on all four nodes
and localhost.

This validates convergence on the existing deployment. A complete rebuild
from fresh VMs has not yet been tested with this consolidated workflow.

This procedure provisions and configures infrastructure. It does not
restore application data.

## Execution environment

Run commands from Ubuntu WSL, at the repository root.

The workflow uses:

- Terraform 1.17.0.
- Python 3.12 with virtual environment support.
- Ansible Core 2.21.5, installed through `ansible/requirements.txt`.
- kubernetes.core 6.6.0, declared in `ansible/requirements.yml`.
- Helm 3.20.1.
- helm-diff 3.15.15.
- kubectl 1.35.3, used with Kubernetes 1.36.5.
- SSH access to the nodes as `ubuntu`, with passwordless sudo.

The versions above describe the validated administration environment.
The Helm, kubectl, and Terraform binaries must already be installed.

## Infrastructure prerequisites

Before provisioning, ensure that:

- Proxmox and OPNsense are operational.
- The Proxmox API is reachable at `https://192.168.0.199:8006/`.
- VLAN 20 is available on `vmbr1`.
- Gateway and DNS service are available at `10.10.20.1`.
- Node addresses `.11`, `.21`, `.22`, and `.23` are available in
  `10.10.20.0/24`.
- The DHCP pool remains outside the static node allocation.
- The verified Ubuntu image is available as
  `local:import/ubuntu-24.04-server-cloudimg-amd64-20261017.qcow2`.
- The Terraform account and token have the documented permissions.
- The API token has not expired.
- The Proxmox CA certificate is available at `private/pve-root-ca.pem`.
- The dedicated SSH key exists at `~/.ssh/homelab_v2_ed25519`, with
  its public key at the corresponding `.pub` path.

Image preparation, API permissions, and initial trust verification are
documented in `proxmox-bootstrap.md`.

## Prepare local Ansible dependencies

Create the virtual environment if it does not already exist:

```bash
python3 -m venv .venv
```

Install the declared dependencies:

```bash
.venv/bin/python -m pip install -r ansible/requirements.txt

.venv/bin/ansible-galaxy collection install \
  -r ansible/requirements.yml
```

Inspect the Helm plugins:

```bash
helm plugin list
```

If the diff plugin is absent, install the validated version:

```bash
helm plugin install https://github.com/databus23/helm-diff \
  --version v3.15.15
```

Verify the local tools:

```bash
terraform version
.venv/bin/ansible --version
.venv/bin/ansible-galaxy collection list kubernetes.core
helm version --short
helm diff version
kubectl version --client
```

Ansible collections are installed separately from the Python virtual
environment, normally under `~/.ansible/collections`.

## Prepare SSH authentication

Inspect the current SSH agent:

```bash
ssh-add -l
```

If no agent is available, start one:

```bash
eval "$(ssh-agent -s)"
```

Load the dedicated key:

```bash
ssh-add -t 1h ~/.ssh/homelab_v2_ed25519
```

A rebuilt VM has a new SSH host identity. Verify the new host-key
fingerprint through a trusted channel before replacing an old
`known_hosts` entry. Do not disable host-key checking globally.

## Provision the VMs with Terraform

Load the API token into the current Bash session:

```bash
read -r -s -p "Proxmox API token secret: " proxmox_token_secret
printf '\n'
export PROXMOX_VE_API_TOKEN='terraform@pve!homelab-v2='"${proxmox_token_secret}"
unset proxmox_token_secret

export SSL_CERT_FILE="$PWD/private/pve-root-ca.pem"
```

Initialize Terraform without requesting a provider upgrade:

```bash
terraform -chdir=terraform init
terraform -chdir=terraform validate
```

Generate a new plan:

```bash
terraform -chdir=terraform plan \
  -parallelism=1 \
  -out=provision.tfplan
```

Review the proposed actions before applying. On an unchanged existing
deployment, no resource changes are expected.

Apply only the plan just reviewed:

```bash
terraform -chdir=terraform apply \
  -parallelism=1 \
  provision.tfplan
```

Applying a saved plan does not ask for another confirmation.

Do not reuse plans from earlier provisioning attempts. After a partial
failure, diagnose the failure and generate a new plan.

Terraform state is local and sensitive. Preserve the current state when
managing existing resources. Do not delete state to force a rebuild or
assume that a fresh checkout can adopt existing VMs automatically.

This procedure does not include a blanket destroy operation. Replacing
existing VMs requires a separate, reviewed plan and a data recovery plan
where applicable.

## Configure the cluster

Verify access to all four nodes:

```bash
.venv/bin/ansible kubernetes \
  -i ansible/inventory.yml \
  -m ansible.builtin.ping
```

Validate the consolidated playbook:

```bash
.venv/bin/ansible-playbook \
  -i ansible/inventory.yml \
  ansible/site.yml \
  --syntax-check
```

Run the complete configuration workflow:

```bash
.venv/bin/ansible-playbook \
  -i ansible/inventory.yml \
  ansible/site.yml
```

The entry point runs these stages in order:

1. Install and start the QEMU Guest Agent.
2. Prepare swap and IPv4 forwarding settings.
3. Configure containerd.
4. Install and hold the Kubernetes packages.
5. Initialize a fresh control plane or verify the existing one.
6. Join workers or verify their registration.
7. Retrieve the administrator kubeconfig into WSL.
8. Install or reconcile Cilium.
9. Check node readiness and the CoreDNS rollout.

Use the complete workflow on fresh hosts. Tags select stages but do not
resolve their dependencies.

## Existing and partial cluster states

The control-plane playbook checks initialization markers before acting.

- With no detected markers, it validates the configuration and runs
  `kubeadm init`.
- With the expected markers present, it checks API readiness.
- With inconsistent markers, it stops for investigation.
- It never runs `kubeadm reset` automatically.

The worker playbook skips joining when `kubelet.conf` already exists and
checks that the node is registered in the API. A partial join can still
require manual diagnosis.

These checks are safeguards, not a general recovery mechanism. The
workflow does not automatically repair partial clusters or implement
Kubernetes upgrades.

## Local cluster access

The workflow writes:

`private/homelab-v2.kubeconfig`

The private directory uses mode `0700`; the kubeconfig uses mode `0600`.
The file contains privileged credentials and must remain excluded from Git.

For interactive administration:

```bash
export KUBECONFIG="$PWD/private/homelab-v2.kubeconfig"

git check-ignore private/homelab-v2.kubeconfig
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
```

Ansible passes the kubeconfig path explicitly to Helm and its local
verification commands, so those tasks do not depend on this export.

## Cilium certificate management

Cilium is pinned to chart version 1.20.4.

Hubble certificate generation uses:

```yaml
hubble:
  tls:
    auto:
      enabled: true
      method: cronJob
```

The original Helm-based certificate generation produced changing Secret
content during rendering, triggering repeated upgrades with helm-diff.

The CronJob method moves certificate generation into the cluster. The
initial generation Job completed successfully, and the subsequent Ansible
run reported zero changes.

The scheduled renewal has not yet been observed executing. Hubble TLS
does not encrypt application traffic carried by VXLAN.

## Functional network validation

Node readiness alone is not proof of working application traffic.

Deploy the repository smoke test:

```bash
kubectl apply -f kubernetes/tests/network-smoke.yml

kubectl wait -n network-smoke \
  --for=condition=Ready pod/server pod/client \
  --timeout=180s

kubectl get pods -n network-smoke -o wide
```

Verify DNS:

```bash
kubectl exec -n network-smoke client -- \
  nslookup server.network-smoke.svc.cluster.local
```

Verify direct cross-node HTTP:

```bash
server_pod_ip="$(kubectl get pod server -n network-smoke \
  -o jsonpath='{.status.podIP}')"

kubectl exec -n network-smoke client -- \
  wget -T 5 -qO- "http://${server_pod_ip}:8080"
```

Verify HTTP through the Service:

```bash
kubectl exec -n network-smoke client -- \
  wget -T 5 -qO- http://server.network-smoke.svc.cluster.local
```

Both HTTP requests must return:

```text
homelab-network-ok
```

Record the actual results before removing the test resources:

```bash
kubectl delete -f kubernetes/tests/network-smoke.yml
```

A successful cleanup is not evidence that the traffic tests passed.

## Remaining validation

- Complete provisioning and configuration from fresh VMs.
- Recovery from partial initialization and worker-join failures.
- Off-host protection of Terraform state.
- Kubernetes and application backup restoration.
- Scheduled Hubble certificate renewal.
- Network isolation and failure scenarios.
