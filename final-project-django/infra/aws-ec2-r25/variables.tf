variable "run_id" {
  description = "Unique identifier within AWS account"
  type        = string
  default     = "20261119"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.run_id))
    error_message = "run_id may contain only lowercase letters, digits, and hyphens."
  }
}
variable "admin_cidr" {
  description = "Current trusted public IPv4/32, never an open range"
  type        = string
  validation {
    condition = (
      can(cidrhost(var.admin_cidr, 0)) &&
      can(regex("^[0-9.]+/32$", var.admin_cidr)) &&
      var.admin_cidr != "0.0.0.0/32"
    )
    error_message = "Provide a single valid IPv4 /32 address for SSH."
  }
}
variable "ssh_public_key_path" {
  description = "Absolute path to existing local OpenSSH public .pub key"
  type        = string
  validation {
    condition     = endswith(var.ssh_public_key_path, ".pub")
    error_message = "Only a pre-existing .pub key can be imported."
  }
}
