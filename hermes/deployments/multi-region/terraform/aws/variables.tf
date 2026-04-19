# Variables for multi-region AWS deployment

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = can(regex("^(staging|production|development)$", var.environment))
    error_message = "Environment must be one of: staging, production, development"
  }
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "hermes-ai.com"

  validation {
    condition     = can(regex("^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.domain_name))
    error_message = "Domain name must be a valid domain name"
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "hermes"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens"
  }
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {
    Terraform = "true"
  }
}

# Region-specific variables
variable "aws_regions" {
  description = "AWS regions for deployment"
  type        = list(string)
  default     = ["us-west-2", "us-east-1", "eu-west-1"]

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.aws_regions))
    error_message = "Region names must be valid AWS region codes"
  }
}

# VPC configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC in primary region"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr)) && can(cidrnetmask(var.vpc_cidr)) && cidrhost(var.vpc_cidr) == 10 && cidrnetmask(var.vpc_cidr) == 16
    error_message = "VPC CIDR must be 10.0.0.0/16"
  }
}

variable "enable_flow_logs" {
  description = "Enable VPC flow logs"
  type        = bool
  default     = true
}

# SSL/TLS configuration
variable "ssl_certificate_arn" {
  description = "ARN of existing SSL certificate (leave null to create new one)"
  type        = string
  default     = null
}

variable "enable_certificate_validation" {
  description = "Enable DNS validation for SSL certificate"
  type        = bool
  default     = true
}

# Database configuration
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"

  validation {
    condition     = can(regex("^\\d+\\.\\d+$", var.postgres_version))
    error_message = "PostgreSQL version must be in format X.Y"
  }
}

variable "postgres_instance_class" {
  description = "PostgreSQL instance class"
  type        = string
  default     = "db.r6g.large"

  validation {
    condition     = can(regex("^db\\.[a-z0-9]+\\.[a-z0-9]+$", var.postgres_instance_class))
    error_message = "Instance class must be in format db.<family>.<size>"
  }
}

variable "postgres_allocated_storage" {
  description = "Allocated storage for PostgreSQL (GB)"
  type        = number
  default     = 100

  validation {
    condition     = var.postgres_allocated_storage >= 20 && var.postgres_allocated_storage <= 65536
    error_message = "Allocated storage must be between 20 GB and 65536 GB"
  }
}

variable "postgres_multi_az" {
  description = "Enable Multi-AZ for PostgreSQL"
  type        = bool
  default     = true
}

# Redis configuration
variable "redis_engine" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.r6g.large"

  validation {
    condition     = can(regex("^cache\\.[a-z0-9]+\\.[a-z0-9]+$", var.redis_node_type))
    error_message = "Node type must be in format cache.<family>.<size>"
  }
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 3

  validation {
    condition     = var.redis_num_cache_nodes >= 1 && var.redis_num_cache_nodes <= 6
    error_message = "Number of cache nodes must be between 1 and 6"
  }
}

# Application configuration
variable "instance_type" {
  description = "EC2 instance type for application"
  type        = string
  default     = "m5.large"

  validation {
    condition     = can(regex("^[a-z][a-z0-9.]+\\.[a-z0-9]+$", var.instance_type))
    error_message = "Instance type must be a valid EC2 instance type"
  }
}

variable "min_capacity" {
  description = "Minimum number of instances"
  type        = number
  default     = 3

  validation {
    condition     = var.min_capacity >= 1
    error_message = "Minimum capacity must be at least 1"
  }
}

variable "max_capacity" {
  description = "Maximum number of instances"
  type        = number
  default     = 10

  validation {
    condition     = var.max_capacity >= var.min_capacity
    error_message = "Maximum capacity must be greater than or equal to minimum capacity"
  }
}

# Monitoring and alerting
variable "enable_cloudwatch" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

variable "sns_email" {
  description = "Email address for SNS notifications"
  type        = string
  default     = ""

  validation {
    condition     = var.sns_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.sns_email))
    error_message = "Email must be a valid email address"
  }
}

# Backup configuration
variable "backup_retention_days" {
  description = "Retention period for backups in days"
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 365
    error_message = "Backup retention must be between 1 and 365 days"
  }
}

variable "backup_schedule" {
  description = "Cron schedule for automated backups"
  type        = string
  default     = "0 2 * * *"  # Daily at 2 AM UTC

  validation {
    condition     = can(regex("^[0-9\\s\\*\\-/]+$", var.backup_schedule))
    error_message = "Backup schedule must be a valid cron expression"
  }
}

# Cost optimization
variable "spot_instance_percentage" {
  description = "Percentage of instances that can be Spot instances"
  type        = number
  default     = 30

  validation {
    condition     = var.spot_instance_percentage >= 0 && var.spot_instance_percentage <= 100
    error_message = "Spot instance percentage must be between 0 and 100"
  }
}

variable "enable_reserved_instances" {
  description = "Enable Reserved Instances for cost savings"
  type        = bool
  default     = true
}

# Security configuration
variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit"
  type        = bool
  default     = true
}

variable "enable_ddos_protection" {
  description = "Enable AWS Shield Advanced Protection"
  type        = bool
  default     = false

  validation {
    condition     = var.enable_ddos_protection == false
    error_message = "AWS Shield Advanced Protection requires manual enrollment"
  }
}

# Compliance
variable "enable_cis_compliance" {
  description = "Enable CIS compliance controls"
  type        = bool
  default     = true
}

variable "enable_pci_compliance" {
  description = "Enable PCI DSS compliance controls"
  type        = bool
  default     = false
}

variable "enable_hipaa_compliance" {
  description = "Enable HIPAA compliance controls"
  type        = bool
  default     = false
}

# Advanced features
variable "enable_multi_az_deployment" {
  description = "Enable multi-AZ deployment for high availability"
  type        = bool
  default     = true
}

variable "enable_auto_scaling" {
  description = "Enable auto scaling"
  type        = bool
  default     = true
}

variable "enable_rolling_updates" {
  description = "Enable rolling updates with zero downtime"
  type        = bool
    default     = true
}

variable "enable_blue_green_deployment" {
  description = "Enable blue-green deployment strategy"
  type        = bool
    default     = false
}

# Regional configuration
variable "region_configs" {
  description = "Region-specific configurations"
  type = object({
    us_west_2 = optional(object({
      min_capacity = optional(number)
      max_capacity = optional(number)
      instance_type = optional(string)
      enable_spot = optional(bool)
    }), {})
    us_east_1 = optional(object({
      min_capacity = optional(number)
      max_capacity = optional(number)
      instance_type = optional(string)
      enable_spot = optional(bool)
    }), {})
    eu_west_1 = optional(object({
      min_capacity = optional(number)
      max_capacity = optional(number)
      instance_type = optional(string)
      enable_spot = optional(bool)
    }), {})
  })
  default = {}
}