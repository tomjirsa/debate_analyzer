# Web App Infrastructure (separate state)

This directory provisions the **web app** (ECS Fargate, RDS, ALB) with its **own Terraform state**, independent of the Batch/S3 stack in `../terraform/`.

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured
- **Existing Batch stack** applied first (you need the S3 bucket name for the web app to read transcripts)

## Variables

- **`aws_region`** (default: eu-central-1)
- **`name_prefix`** (default: debate-analyzer-webapp)
- **`vpc_id`** (optional) – VPC for ECS and RDS; if null, default VPC is used
- **`subnet_ids`** (optional) – Subnets for ECS tasks; if null, all subnets in the VPC
- **`existing_s3_bucket_name`** – Name of the S3 bucket from the Batch stack (transcripts bucket)
- **`admin_username`** – HTTP Basic auth username for admin (sensitive)
- **`admin_password`** – HTTP Basic auth password (sensitive)
- **`db_password`** – Master password for RDS (sensitive)

Provide via `terraform.tfvars` (do not commit) or `TF_VAR_*` environment variables.

## Backend

By default state is stored locally in `deploy/terraform-webapp/terraform.tfstate`. For production, configure a remote backend (e.g. S3 + DynamoDB) in a `backend` block and run `terraform init -reconfigure`.

## Usage

```bash
cd deploy/terraform-webapp
terraform init
terraform plan -var="existing_s3_bucket_name=YOUR_BUCKET" -var="admin_username=admin" -var="admin_password=CHANGE_ME" -var="db_password=CHANGE_ME"
terraform apply  # same vars
```

After apply, build and push the **web app** Docker image to the ECR repository created here, then update the ECS service (or use CI/CD). The app expects `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and optionally `AWS_S3_BUCKET` (or use IAM role to discover bucket).

## Outputs

- **`alb_dns_name`** – ALB DNS name (use with HTTPS or point a CNAME here)
- **`rds_endpoint`** – RDS instance endpoint (for `DATABASE_URL`)
- **`ecr_repository_url`** – ECR repo for the web app image
