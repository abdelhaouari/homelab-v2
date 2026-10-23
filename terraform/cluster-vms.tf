locals {
  cluster_nodes = {
    k8s-cp01 = {
      vm_id   = 201
      address = "10.10.20.11/24"
      memory  = 4096
      disk    = 60
    }
    k8s-worker01 = {
      vm_id   = 202
      address = "10.10.20.21/24"
      memory  = 8192
      disk    = 80
    }
    k8s-worker02 = {
      vm_id   = 203
      address = "10.10.20.22/24"
      memory  = 8192
      disk    = 80
    }
    k8s-worker03 = {
      vm_id   = 204
      address = "10.10.20.23/24"
      memory  = 8192
      disk    = 80
    }
  }
}

resource "proxmox_virtual_environment_vm" "cluster" {
  for_each = local.cluster_nodes

  name        = each.key
  description = "Kubernetes lab node. Managed by Terraform."
  node_name   = "pve"
  vm_id       = each.value.vm_id

  started    = true
  on_boot    = false
  boot_order = ["scsi0"]

  cpu {
    cores = 2
    type  = "host"
  }

  memory {
    dedicated = each.value.memory
  }

  agent {
    enabled = true

    wait_for_ip {
      disabled = true
    }
  }

  disk {
    datastore_id = "local-zfs"
    interface    = "scsi0"
    file_format  = "raw"
    size         = each.value.disk
    import_from  = "local:import/ubuntu-24.04-server-cloudimg-amd64-20261017.qcow2"
  }

  network_device {
    bridge  = "vmbr1"
    model   = "virtio"
    vlan_id = 20
  }

  initialization {
    datastore_id = "local-zfs"

    dns {
      servers = ["10.10.20.1"]
    }

    ip_config {
      ipv4 {
        address = each.value.address
        gateway = "10.10.20.1"
      }
    }

    user_account {
      username = "ubuntu"
      keys = [
        trimspace(file(pathexpand("~/.ssh/homelab_v2_ed25519.pub")))
      ]
    }
  }

  operating_system {
    type = "l26"
  }

  serial_device {}
}
