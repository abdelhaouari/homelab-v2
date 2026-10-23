data "proxmox_virtual_environment_nodes" "available" {}

output "proxmox_node_names" {
  description = "Proxmox node names returned by the API."
  value       = data.proxmox_virtual_environment_nodes.available.names
}