# AWS Setup Guide (Step-by-Step)

This guide walks through setting up the Debate Analyzer on AWS: the **Batch stack** (download + transcribe pipeline) and optionally the **Web app stack** (ECS, RDS, ALB). Both use Terraform with **separate state**; apply the Batch stack first because the web app needs the S3 bucket name.

For a visual overview of the AWS deployment, see [ARCHITECTURE_AWS.md](ARCHITECTURE_AWS.md). For job submission details and two-job flow, see [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md).

---

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) configured (or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION`)
- **HuggingFace account and token** (for speaker diarization): create at [huggingface.co](https://huggingface.co), accept terms at [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1), create token at [settings/tokens](https://huggingface.co/settings/tokens)
- Optional: YouTube cookies (Netscape format) if you hit "Sign in to confirm you're not a bot" when downloading from AWS

---

## Order of Operations

1. **Apply Batch stack** (`deploy/terraform/`) — creates S3, ECR, Secrets Manager, Batch (GPU/CPU), job definitions.
2. **Build and push pipeline image** to ECR (GitHub Actions or local Docker).
3. **Submit Batch jobs** (full pipeline or download then transcribe) — see [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md).
4. *(Optional)* **Apply Web app stack** (`deploy/terraform-webapp/`) — needs S3 bucket name from step 1; creates RDS, ECS Fargate, ALB.
5. *(Optional)* **Build and push web app image** to the web app ECR repo; force ECS deployment to use new image.

---

## Part 1: Batch Stack (`deploy/terraform/`)

### Terraform Variables (Batch)

Provide required variables via `TF_VAR_*` environment variables, or a `terraform.tfvars` file (do **not** commit secrets).

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `aws_region` | string | `eu-central-1` | AWS region for all resources. |
| `name_prefix` | string | `debate-analyzer` | Prefix for resource names. |
| **`hf_token`** | string | *(required)* | HuggingFace token for pyannote; stored in Secrets Manager. Use `TF_VAR_hf_token` or tfvars. Never commit. |
| `yt_cookies_secret_arn` | string | `null` | ARN of Secrets Manager secret with YouTube cookies (Netscape format). Optional; for bot check. |
| `yt_cookies_file_path` | string | `null` | Path to local `cookies.txt` (Netscape format). If set, Terraform creates the secret from this file. Do not commit. |
| `ecr_image_tag` | string | `latest` | Docker image tag used in the Batch job definition. |
| `batch_compute_instance_types` | list(string) | `["g4dn.xlarge", "g4dn.2xlarge"]` | EC2 instance types for GPU compute environment. |
| `batch_min_vcpus` | number | `0` | Min vCPUs for GPU compute environment (0 = scale to zero). |
| `batch_max_vcpus` | number | `256` | Max vCPUs for GPU compute environment. |
| `batch_cpu_instance_types` | list(string) | `["c5.xlarge"]` | EC2 instance types for CPU compute environment (download job). |
| `batch_cpu_min_vcpus` | number | `0` | Min vCPUs for CPU compute environment. |
| `batch_cpu_max_vcpus` | number | `64` | Max vCPUs for CPU compute environment. |
| `vpc_id` | string | `null` | VPC ID; if null, default VPC is used. |
| `subnet_ids` | list(string) | `null` | Subnet IDs; if null, default VPC subnets are used. |
| `use_spot` | bool | `false` | Use Spot instances for Batch (may be interrupted). |

### Steps: Init, Plan, Apply (Batch)

From the repository root:

```bash
# Set required secret (never commit)
export TF_VAR_hf_token="your_huggingface_token"

cd deploy/terraform
terraform init
terraform plan    # review resources
terraform apply   # type yes when prompted
```

After apply, note the outputs (e.g. `terraform output`):

- `batch_job_queue_name` — GPU queue (full pipeline + transcribe job)
- `batch_job_queue_cpu_name` — CPU queue (download job)
- `batch_job_definition_name` — full pipeline job definition
- `batch_job_definition_download_name` — download-only job definition
- `batch_job_definition_transcribe_name` — transcribe-only job definition
- `s3_bucket_name` — bucket for videos and transcripts
- `ecr_repository_url` — where to push the pipeline Docker image

### Build and Push Pipeline Image

**Option A: GitHub Actions** (recommended)

1. In the repo: **Settings → Secrets and variables → Actions**.
2. **AWS credentials:** Either add `AWS_ROLE_ARN` (OIDC) or `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
3. **Region:** Set variable `AWS_REGION` (e.g. `eu-central-1`) if not using the workflow default.
4. Push to `main` or run the workflow manually. The workflow builds from the root `Dockerfile` and pushes to the ECR repo (`debate-analyzer:latest`).

**Option B: Local Docker**

```bash
REGION=$(cd deploy/terraform && terraform output -raw aws_region)
ACCOUNT=$(cd deploy/terraform && terraform output -raw aws_caller_identity_account_id)
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
docker build -t "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/debate-analyzer:latest" .
docker push "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/debate-analyzer:latest"
```

### Submit a Job (Quick Reference)

- **Full pipeline (one job):** `./deploy/scripts/submit-jobs/submit-job.sh "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"`
- **Two jobs (download then transcribe):** See [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md#4b-two-job-flow-download-then-transcribe).

---

## Part 2: Web App Stack (`deploy/terraform-webapp/`)

Apply this **after** the Batch stack. The web app reads transcripts from the S3 bucket created by the Batch stack.

### Prerequisites (Web App)

- Batch stack applied; you need **S3 bucket name** (e.g. `terraform output -raw s3_bucket_name` from `deploy/terraform`).
- IAM user/role running Terraform must have permissions for RDS, ECS, Secrets Manager, EC2 (VPC/security groups), ECR, IAM (ECS roles), ELB, CloudWatch. Attach the policy in `deploy/terraform-webapp/iam-policy-terraform-webapp.json` if needed.
- **RDS service-linked role:** If you see an error about creating it, run once (e.g. as admin): `aws iam create-service-linked-role --aws-service-name rds.amazonaws.com`

### Terraform Variables (Web App)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `aws_region` | string | `eu-central-1` | AWS region for web app resources. |
| `name_prefix` | string | `debate-analyzer-webapp` | Prefix for resource names. |
| `vpc_id` | string | `null` | VPC ID for ECS and RDS; if null, default VPC is used. |
| `subnet_ids` | list(string) | `null` | Subnet IDs for ECS tasks; if null, all subnets in the VPC. |
| **`existing_s3_bucket_name`** | string | *(required)* | Name of the S3 bucket from the Batch stack (transcripts bucket). |
| **`admin_username`** | string | *(required)* | HTTP Basic auth username for admin routes. Sensitive. |
| **`admin_password`** | string | *(required)* | HTTP Basic auth password for admin routes. Sensitive. |
| **`db_password`** | string | *(required)* | Master password for RDS PostgreSQL. Sensitive. |
| `ecr_image_tag` | string | `latest` | Docker image tag for the web app. |

### Steps: Init, Plan, Apply (Web App)

From the repository root:

```bash
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name)

cd deploy/terraform-webapp
terraform init
terraform plan \
  -var="existing_s3_bucket_name=$BUCKET" \
  -var="admin_username=admin" \
  -var="admin_password=CHANGE_ME" \
  -var="db_password=CHANGE_ME"
terraform apply \
  -var="existing_s3_bucket_name=$BUCKET" \
  -var="admin_username=admin" \
  -var="admin_password=CHANGE_ME" \
  -var="db_password=CHANGE_ME"
```

Use a `terraform.tfvars` file (do not commit) for sensitive values instead of `-var` if you prefer.

After apply:

- Build and push the web app image to the ECR repository (see `ecr_repository_url` output). Use `Dockerfile.webapp`; CI can push to `debate-analyzer-webapp:latest`.
- **Reload web app from ECR:** After pushing a new image, force ECS to pull it:

  ```bash
  aws ecs update-service --cluster debate-analyzer-webapp --service debate-analyzer-webapp --force-new-deployment
  ```

  Add `--region <region>` (e.g. `eu-central-1`) if not using your default. Alternatively: AWS Console → ECS → Service → Update service → Force new deployment.

Outputs: `alb_dns_name`, `rds_endpoint`, `ecr_repository_url`.

---

## First-Time AWS Checklist

1. [ ] HuggingFace token created; pyannote model terms accepted.
2. [ ] `export TF_VAR_hf_token="..."` (or tfvars); run `terraform init` and `terraform apply` in `deploy/terraform/`.
3. [ ] Pipeline image built and pushed to ECR (GitHub Actions or local Docker).
4. [ ] Test job: `./deploy/scripts/submit-jobs/submit-job.sh "https://www.youtube.com/watch?v=VIDEO_ID"`; check S3 and CloudWatch logs.
5. [ ] *(Optional)* Run `terraform apply` in `deploy/terraform-webapp/` with `existing_s3_bucket_name` and admin/db passwords.
6. [ ] *(Optional)* Push web app image to web app ECR; force ECS deployment; open ALB URL.

---

## See Also

- [ARCHITECTURE_AWS.md](ARCHITECTURE_AWS.md) — AWS deployment architecture and diagram.
- [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md) — Job submission, two-job flow, YouTube cookies, logs.
- [deploy/terraform/README.md](../deploy/terraform/README.md) — Batch stack quick reference.
- [deploy/terraform-webapp/README.md](../deploy/terraform-webapp/README.md) — Web app stack quick reference.
