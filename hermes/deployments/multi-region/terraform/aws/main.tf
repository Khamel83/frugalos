# Terraform configuration for multi-region AWS deployment
# This manages the global infrastructure for Hermes AI Assistant

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 0.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

# Configure AWS providers for multiple regions
provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"
  default_tags {
    tags = {
      Project     = "hermes-ai-assistant"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  default_tags {
    tags = {
      Project     = "hermes-ai-assistant"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
  default_tags {
    tags = {
      Project     = "hermes-ai-assistant"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Random provider for unique resource naming
resource "random_id" "unique" {
  byte_length = 4
}

# Variables
variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "hermes-ai.com"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "hermes"
}

# Route 53 hosted zone
resource "aws_route53_zone" "primary" {
  name = var.domain_name

  tags = {
    Name = "${var.project_name}-primary-zone"
  }
}

# Create SSL certificate
resource "aws_acm_certificate" "primary" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}",
    "api.${var.domain_name}",
    "*.api.${var.domain_name}"
  ]

  tags = {
    Name = "${var.project_name}-ssl-cert"
  }
}

# DNS validation for certificate
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.primary.domain_validation_options : dvo.domain_name => dvo
  }

  allow_overwrite = true
  name            = each.key
  type            = "CNAME"
  ttl             = 60
  records         = [each.value.resource_record_value]
  zone_id         = aws_route53_zone.primary.zone_id
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "primary" {
  certificate_arn         = aws_acm_certificate.primary.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# S3 buckets for cross-region data synchronization
resource "aws_s3_bucket" "config_sync_us_west_2" {
  provider = aws.us_west_2
  bucket   = "${var.project_name}-config-sync-${random_id.unique.hex}-us-west-2"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default = true
      sse_algorithm = "AES256"
    }
  }

  lifecycle_rule {
    id      = "cleanup"
    enabled = true

    filter {
      prefix = "logs/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 60
      storage_class = "GLACIER"
    }

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 365
    }
  }

  tags = {
    Name = "${var.project_name}-config-sync-us-west-2"
    Type = "ConfigurationSync"
  }
}

resource "aws_s3_bucket" "config_sync_us_east_1" {
  provider = aws.us_east_1
  bucket   = "${var.project_name}-config-sync-${random_id.unique.hex}-us-east-1"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default = true
      sse_algorithm = "AES256"
    }
  }

  replication_configuration {
    role = aws_iam_role.s3_replication.arn
    rules {
      id = "replication"
      destination {
        bucket        = aws_s3_bucket.config_sync_us_west_2.id
        storage_class = "STANDARD"
      }
      delete_marker_replication {
        status = "Enabled"
      }
    }
  }

  tags = {
    Name = "${var.project_name}-config-sync-us-east-1"
    Type = "ConfigurationSync"
  }
}

resource "aws_s3_bucket" "config_sync_eu_west_1" {
  provider = aws.eu_west_1
  bucket   = "${var.project_name}-config-sync-${random_id.unique.hex}-eu-west-1"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default = true
      sse_algorithm = "AES256"
    }
  }

  replication_configuration {
    role = aws_iam_role.s3_replication.arn
    rules {
      id = "replication"
      destination {
        bucket        = aws_s3_bucket.config_sync_us_west_2.id
        storage_class = "STANDARD"
      }
      delete_marker_replication {
        status = "Enabled"
      }
    }
  }

  tags = {
    Name = "${var.project_name}-config-sync-eu-west-1"
    Type = "ConfigurationSync"
  }
}

# S3 bucket for WAL archives
resource "aws_s3_bucket" "postgres_wal" {
  provider = aws.us_west_2
  bucket   = "${var.project_name}-postgres-wal-${random_id.unique.hex}"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default = true
      sse_algorithm = "AES256"
    }
  }

  lifecycle_rule {
    id      = "wal_retention"
    enabled = true

    transition {
      days          = 7
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    expiration {
      days = 90
    }
  }

  tags = {
    Name = "${var.project_name}-postgres-wal"
    Type = "DatabaseWAL"
  }
}

# KMS key for encryption
resource "aws_kms_key" "hermes" {
  provider = aws.us_west_2
  description             = "KMS key for Hermes AI Assistant encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-kms-key"
    Type = "Encryption"
  }
}

# IAM role for S3 replication
resource "aws_iam_role" "s3_replication" {
  name = "${var.project_name}-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-s3-replication-role"
    Type = "IAMRole"
  }
}

resource "aws_iam_policy" "s3_replication" {
  name        = "${var.project_name}-s3-replication-policy"
  description = "Policy for S3 cross-region replication"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket",
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionTagging",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.config_sync_us_west_2.arn,
          "${aws_s3_bucket.config_sync_us_west_2.arn}/*",
          aws_s3_bucket.config_sync_us_east_1.arn,
          "${aws_s3_bucket.config_sync_us_east_1.arn}/*",
          aws_s3_bucket.config_sync_eu_west_1.arn,
          "${aws_s3_bucket.config_sync_eu_west_1.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_replication" {
  role       = aws_iam_role.s3_replication.name
  policy_arn = aws_iam_policy.s3_replication.arn
}

# VPCs in each region
module "vpc_us_west_2" {
  source = "./modules/vpc"
  providers = {
    aws = aws.us_west_2
  }

  region = "us-west-2"
  cidr_block = "10.0.0.0/16"
  name = "${var.project_name}-us-west-2"

  tags = {
    Name = "${var.project_name}-vpc-us-west-2"
    Region = "us-west-2"
  }
}

module "vpc_us_east_1" {
  source = "./modules/vpc"
  providers = {
    aws = aws.us_east_1
  }

  region = "us-east-1"
  cidr_block = "10.1.0.0/16"
  name = "${var.project_name}-us-east-1"

  tags = {
    Name = "${var.project_name}-vpc-us-east-1"
    Region = "us-east-1"
  }
}

module "vpc_eu_west_1" {
  source = "./modules/vpc"
  providers = {
    aws = aws.eu_west_1
  }

  region = "eu-west-1"
  cidr_block = "10.2.0.0/16"
  name = "${var.project_name}-eu-west-1"

  tags = {
    Name = "${var.project_name}-vpc-eu-west-1"
    Region = "eu-west-1"
  }
}

# VPC peering connections
resource "aws_vpc_peering_connection" "us_west_2_to_us_east_1" {
  provider = aws.us_west_2
  vpc_id        = module.vpc_us_west_2.vpc_id
  peer_vpc_id   = module.vpc_us_east_1.vpc_id
  auto_accept   = false

  tags = {
    Name = "${var.project_name}-us-west-2-to-us-east-1"
  }
}

resource "aws_vpc_peering_connection_accepter" "us_east_1_from_us_west_2" {
  provider = aws.us_east_1
  vpc_id        = module.vpc_us_east_1.vpc_id
  pcx_id         = aws_vpc_peering_connection.us_west_2_to_us_east_1.id
  auto_accept   = true

  tags = {
    Name = "${var.project_name}-us-east-1-from-us-west-2"
  }
}

resource "aws_vpc_peering_connection" "us_west_2_to_eu_west_1" {
  provider = aws.us_west_2
  vpc_id        = module.vpc_us_west_2.vpc_id
  peer_vpc_id   = module.vpc_eu_west_1.vpc_id
  auto_accept   = false

  tags = {
    Name = "${var.project_name}-us-west-2-to-eu-west-1"
  }
}

resource "aws_vpc_peering_connection_accepter" "eu_west_1_from_us_west_2" {
  provider = aws.eu_west_1
  vpc_id        = module.vpc_eu_west_1.vpc_id
  pcx_id         = aws_vpc_peering_connection.us_west_2_to_eu_west_1.id
  auto_accept   = true

  tags = {
    Name = "${var.project_name}-eu-west-1-from-us-west-2"
  }
}

# Route tables for VPC peering
resource "aws_route" "us_west_2_to_us_east_1" {
  provider = aws.us_west_2
  route_table_id         = module.vpc_us_west_2.private_route_table_ids[0]
  destination_cidr_block = module.vpc_us_east_1.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.us_west_2_to_us_east_1.id
}

resource "aws_route" "us_west_2_to_eu_west_1" {
  provider = aws.us_west_2
  route_table_id         = module.vpc_us_west_2.private_route_table_ids[0]
  destination_cidr_block = module.vpc_eu_west_1.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.us_west_2_to_eu_west_1.id
}

resource "aws_route" "us_east_1_to_us_west_2" {
  provider = aws.us_east_1
  route_table_id         = module.vpc_us_east_1.private_route_table_ids[0]
  destination_cidr_block = module.vpc_us_west_2.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.us_west_2_to_us_east_1.id
}

resource "aws_route" "eu_west_1_to_us_west_2" {
  provider = aws.eu_west_1
  route_table_id         = module.vpc_eu_west_1.private_route_table_ids[0]
  destination_cidr_block = module.vpc_us_west_2.vpc_cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.us_west_2_to_eu_west_1.id
}

# CloudWatch alarm for cross-region monitoring
resource "aws_cloudwatch_metric_alarm" "region_health_check" {
  for_each = {
    for region in ["us-west-2", "us-east-1", "eu-west-1"] : region => region
  }

  alarm_name          = "${var.project_name}-${each.key}-health-check"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "HermesAI"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Health check failed for ${each.key} region"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    Region = each.key
  }

  tags = {
    Name = "${var.project_name}-${each.key}-health-check"
    Type = "HealthCheck"
    Region = each.key
  }
}

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"

  tags = {
    Name = "${var.project_name}-alerts"
    Type = "Alerts"
  }
}

# Outputs
output "hosted_zone_id" {
  description = "Route 53 hosted zone ID"
  value       = aws_route53_zone.primary.zone_id
}

output "certificate_arn" {
  description = "SSL certificate ARN"
  value       = aws_acm_certificate.primary.arn
}

output "config_sync_buckets" {
  description = "S3 buckets for configuration sync"
  value = {
    us_west_2 = aws_s3_bucket.config_sync_us_west_2.id
    us_east_1 = aws_s3_bucket.config_sync_us_east_1.id
    eu_west_1 = aws_s3_bucket.config_sync_eu_west_1.id
  }
}

output "postgres_wal_bucket" {
  description = "S3 bucket for PostgreSQL WAL archives"
  value       = aws_s3_bucket.postgres_wal.id
}

output "kms_key_arn" {
  description = "KMS key ARN"
  value       = aws_kms_key.hermes.arn
}

output "vpc_ids" {
  description = "VPC IDs for each region"
  value = {
    us_west_2 = module.vpc_us_west_2.vpc_id
    us_east_1 = module.vpc_us_east_1.vpc_id
    eu_west_1 = module.vpc_eu_west_1.vpc_id
  }
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}