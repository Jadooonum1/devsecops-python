variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Name prefix for every resource"
  type        = string
  default     = "shelflend"
}

variable "owner" {
  description = "Owner tag"
  type        = string
  default     = "parth-agarwal"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.40.0.0/16"
}

variable "az_count" {
  description = "How many availability zones (one public + one private subnet each)"
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "EKS needs subnets in at least two AZs; this module supports 2 or 3."
  }
}

variable "enable_nat_gateway" {
  description = "Create a NAT gateway so nodes in private subnets reach the internet"
  type        = bool
  default     = true
}

variable "cluster_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.34"
}

variable "api_allowed_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  description = "Instance types for the managed node group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired" {
  type    = number
  default = 2
}

variable "node_min" {
  type    = number
  default = 1
}

variable "node_max" {
  type    = number
  default = 3
}
