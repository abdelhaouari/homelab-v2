# Proxmox Terraform bootstrap

## Configuration

- Terraform CLI: 1.17.0 on Linux AMD64.
- Provider: bpg/proxmox 0.117.0.
- API endpoint: https://192.168.0.199:8006/.
- TLS verification remains enabled.
- The Proxmox CA certificate is stored locally in private/pve-root-ca.pem.
- Its SHA-256 fingerprint was compared with the certificate on the Proxmox host.
- SSL_CERT_FILE supplies the CA certificate to the Terraform process.
- API authentication uses PROXMOX_VE_API_TOKEN, entered interactively.
- No token secret is stored in the Terraform configuration.

## Initial permissions

The terraform@pve user and its homelab-v2 token have the
TerraformNodeRead role on /nodes/pve, without propagation.

The role contains only Sys.Audit. Token privilege separation is enabled.
The token was created with a 30-day expiration.

## Observed validation

- Terraform initialization installed the selected provider.
- Terraform configuration validation succeeded.
- An HTTPS request using the Proxmox CA certificate returned HTTP 200.
- Terraform successfully read proxmox_virtual_environment_nodes.
- The planned proxmox_node_names output contained pve.
- No apply was run and no infrastructure was changed.
- A GET request to /api2/json/nodes/pve/qemu/100/config returned HTTP 403.
- The response identified the missing VM.Audit privilege on /vms/100.
- This confirms that the token cannot read the OPNsense VM configuration.

## Remaining validation

- Define and grant the permissions needed for the first disposable VM.
- Provision and validate that VM.
