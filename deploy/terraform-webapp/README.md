# Web App Infrastructure (separate state)

This directory provisions the **web app** (ECS Fargate, RDS, ALB) with its **own Terraform state**, independent of the Batch/S3 stack in `../terraform/`.

For a **step-by-step AWS setup** and full variable descriptions, see [doc/AWS_SETUP.md](../../doc/AWS_SETUP.md). For the **AWS deployment architecture** (Batch and Web app stacks), see [doc/ARCHITECTURE_AWS.md](../../doc/ARCHITECTURE_AWS.md).

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured
- **Existing Batch stack** applied first (you need the S3 bucket name for the web app to read transcripts)
- **IAM user/role** used to run Terraform (e.g. `DatabaseAnalyzer`) must have permissions for RDS, ECS, Secrets Manager, EC2 (VPC/security groups), ECR, IAM (roles for ECS), ELB, and CloudWatch Logs. If you see `AccessDenied` for `rds:CreateDBSubnetGroup` or `ecs:CreateCluster`, attach the policy in `iam-policy-terraform-webapp.json` to that user:

  ```bash
  # Create a policy in AWS from the JSON file (one-time)
  aws iam create-policy \
    --policy-name DebateAnalyzerWebappTerraform \
    --policy-document file://deploy/terraform-webapp/iam-policy-terraform-webapp.json

  # Attach to the user you use for Terraform (replace ACCOUNT_ID and DatabaseAnalyzer if different)
  aws iam attach-user-policy \
    --user-name DatabaseAnalyzer \
    --policy-arn arn:aws:iam::ACCOUNT_ID:policy/DebateAnalyzerWebappTerraform
  ```

  Replace `ACCOUNT_ID` with your AWS account ID (e.g. `135247151294`). Then re-run `terraform apply`.

- **RDS “service linked role”**: If RDS fails with `InvalidParameterValue: Unable to create the resource. Verify that you have permission to create service linked role`, the RDS service-linked role does not exist yet in the account. Either:

  1. **One-time (recommended)** – create it with an identity that can create service-linked roles (e.g. root or admin), then re-run Terraform with your usual user:

     ```bash
     aws iam create-service-linked-role --aws-service-name rds.amazonaws.com
     ```

     If the role already exists you will get “has been taken”; that’s fine. Then run `terraform apply` again.

  2. **Or** – an admin attaches the minimal policy `iam-inline-rds-slr.json` to the Terraform user (e.g. as an inline policy), then you run `terraform apply` again so RDS can create the role:

     ```bash
     # As admin:
     aws iam put-user-policy --user-name DatabaseAnalyzer --policy-name RDS-ServiceLinkedRole --policy-document file://deploy/terraform-webapp/iam-inline-rds-slr.json
     ```

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
