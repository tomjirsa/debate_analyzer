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

After apply, the **web app** Docker image must be available in the ECR repository. Either build and push manually (see repo root) or use CI/CD.

**GitHub Actions:** The workflow `.github/workflows/build-push-ecr.yml` builds both the pipeline image and the web app image (`Dockerfile.webapp`) and pushes the web app to this stack’s ECR repo (`debate-analyzer-webapp:latest`) on push to `main`. The IAM role used by GitHub Actions (`AWS_ROLE_ARN`) must be allowed to push to **both** ECR repositories (`debate-analyzer` and `debate-analyzer-webapp`). If the role was created only for the Batch stack, add an ECR policy granting `ecr:GetAuthorizationToken` and (on the web app repo) `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload` for the `debate-analyzer-webapp` repository.

Then force a new ECS deployment so the service pulls the latest image. The app expects `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (injected by the task definition).

## Outputs

- **`alb_dns_name`** – ALB DNS name (use with HTTPS or point a CNAME here)
- **`rds_endpoint`** – RDS instance endpoint (for `DATABASE_URL`)
- **`ecr_repository_url`** – ECR repo for the web app image
