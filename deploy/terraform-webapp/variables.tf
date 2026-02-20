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
