variable "aws_region" {
  description = "AWS region for web app resources."
  type        = string
  default     = "eu-central-1"
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "debate-analyzer-webapp"
}

variable "vpc_id" {
  description = "VPC ID for ECS and RDS. If null, default VPC is used."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Subnet IDs for ECS tasks. If null, all subnets in the VPC."
  type        = list(string)
  default     = null
}

variable "existing_s3_bucket_name" {
  description = "Name of the S3 bucket (from Batch stack) where transcripts are stored."
  type        = string
}

variable "admin_username" {
  description = "HTTP Basic auth username for admin routes."
  type        = string
  sensitive   = true
}

variable "admin_password" {
  description = "HTTP Basic auth password for admin routes."
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password for RDS PostgreSQL."
  type        = string
  sensitive   = true
}

variable "ecr_image_tag" {
  description = "Docker image tag for the web app."
  type        = string
  default     = "latest"
}

variable "cloudfront_speaker_photos_url" {
  description = "Base URL for speaker profile photos (e.g. https://d123.cloudfront.net from Batch stack output). If null, photo_url will be null in API responses."
  type        = string
  default     = null
}

variable "speaker_photos_s3_bucket" {
  description = "S3 bucket for speaker photo uploads. Defaults to existing_s3_bucket_name when null."
  type        = string
  default     = null
}

variable "rds_publicly_accessible" {
  description = "If true, RDS instance gets a public endpoint. Default is false (DB private, no internet access)."
  type        = bool
  default     = false
}

variable "rds_allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to RDS on port 5432 when rds_publicly_accessible is true (e.g. [\"203.0.113.50/32\"]). Empty = no extra ingress (only ECS). For production, prefer a narrow range (office/VPN) over 0.0.0.0/0."
  type        = list(string)
  default     = []
}
