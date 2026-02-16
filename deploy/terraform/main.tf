terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  name       = var.name_prefix
  # ECR image URI for job definition (CI pushes to this repo)
  ecr_image = "${local.account_id}.dkr.ecr.${local.region}.amazonaws.com/${aws_ecr_repository.this.name}:${var.ecr_image_tag}"
}

# --- Secrets Manager: HuggingFace token ---
resource "aws_secretsmanager_secret" "hf_token" {
  name        = "${local.name}/huggingface-token"
  description = "HuggingFace token for pyannote in debate-analyzer"
}

resource "aws_secretsmanager_secret_version" "hf_token" {
  secret_id     = aws_secretsmanager_secret.hf_token.id
  secret_string = var.hf_token
}

# --- S3: bucket for downloaded videos and transcripts ---
resource "aws_s3_bucket" "output" {
  bucket = "${local.name}-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "output" {
  bucket = aws_s3_bucket.output.id

  versioning_configuration {
    status = "Disabled"
  }
}

# --- IAM: Batch job role (used by the container at runtime) ---
resource "aws_iam_role" "batch_job" {
  name = "${local.name}-batch-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "batch_job" {
  name   = "${local.name}-batch-job-policy"
  role   = aws_iam_role.batch_job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"]
        Resource = [aws_s3_bucket.output.arn, "${aws_s3_bucket.output.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_secretsmanager_secret.hf_token.arn
      }
    ]
  })
}

# --- IAM: Batch execution role (pull image, logs) ---
resource "aws_iam_role" "batch_execution" {
  name = "${local.name}-batch-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_execution_ecr" {
  role       = aws_iam_role.batch_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "batch_execution_logs" {
  role       = aws_iam_role.batch_execution.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# --- IAM: Instance role for Batch compute environment (EC2 hosts) ---
resource "aws_iam_role" "batch_instance" {
  name = "${local.name}-batch-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_instance_ecs" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "batch_instance" {
  name = "${local.name}-batch-instance-profile"
  role = aws_iam_role.batch_instance.name
}

# --- ECR repository ---
resource "aws_ecr_repository" "this" {
  name = local.name
}

# --- VPC / subnets (use default if not provided) ---
data "aws_vpc" "default" {
  count   = var.vpc_id == null ? 1 : 0
  default = true
}

locals {
  selected_vpc_id = var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id
}

data "aws_subnets" "selected" {
  filter {
    name   = "vpc-id"
    values = [local.selected_vpc_id]
  }
}

locals {
  subnet_ids = var.subnet_ids != null ? var.subnet_ids : data.aws_subnets.selected.ids
}

# Security group for Batch compute (outbound only; no hardcoded credentials)
resource "aws_security_group" "batch" {
  name_prefix = "${local.name}-batch-"
  vpc_id      = local.selected_vpc_id
  description = "Security group for debate-analyzer Batch compute"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
}

# --- CloudWatch log group for Batch job logs ---
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/${local.name}"
  retention_in_days  = 14
}

# --- Batch: compute environment ---
resource "aws_batch_compute_environment" "gpu" {
  compute_environment_name = "${local.name}-gpu"
  type                     = "MANAGED"
  state                    = "ENABLED"

  compute_resources {
    type                = "EC2"
    allocation_strategy = var.use_spot ? "SPOT_CAPACITY_OPTIMIZED" : "BEST_FIT"
    min_vcpus           = var.batch_min_vcpus
    max_vcpus           = var.batch_max_vcpus
    instance_type       = var.batch_compute_instance_types
    subnets             = local.subnet_ids
    security_group_ids   = [aws_security_group.batch.id]
    instance_role       = aws_iam_instance_profile.batch_instance.arn
  }
}

# --- Batch: job queue ---
resource "aws_batch_job_queue" "this" {
  name     = "${local.name}-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.gpu.arn
  }
}

# --- Batch: job definition ---
resource "aws_batch_job_definition" "this" {
  name                  = "${local.name}-job"
  type                  = "container"
  platform_capabilities = ["EC2"]

  container_properties = jsonencode({
    image = local.ecr_image
    resourceRequirements = [
      { type = "VCPU", value = "4" },
      { type = "MEMORY", value = "16384" },
      { type = "GPU", value = "1" }
    ]
    jobRoleArn    = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_execution.arn
    secrets = [
      {
        name      = "HF_TOKEN"
        valueFrom = aws_secretsmanager_secret.hf_token.arn
      }
    ]
    environment = []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"         = local.region
        "awslogs-stream-prefix" = "batch"
      }
    }
  })
}
