variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "request_id" {
  type        = string
  description = "ID of the portal request this instance belongs to"
}

variable "instance_type" {
  type        = string
  default     = "t3.micro"
  description = "Only free-plan-eligible types are allowed"

  validation {
    condition     = contains(["t2.micro", "t3.micro", "t3.small", "c7i-flex.large"], var.instance_type)
    error_message = "Only t2.micro, t3.micro, t3.small and c7i-flex.large are allowed in this project."
  }
}

variable "storage_gb" {
  type    = number
  default = 8

  validation {
    condition     = var.storage_gb >= 8 && var.storage_gb <= 30
    error_message = "storage_gb must be between 8 and 30."
  }
}

variable "allowed_cidr" {
  type        = string
  default     = ""
  description = "IP range allowed to use SSH, e.g. 203.0.113.5/32. Empty = SSH closed."
}

variable "instance_name" {
  type        = string
  default     = ""
  description = "Name chosen by the user. Used in the instance Name tag."
}
