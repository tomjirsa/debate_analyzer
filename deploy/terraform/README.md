# Debate Analyzer – AWS Batch (Terraform)

This directory provisions all AWS resources for running the debate-analyzer pipeline on AWS Batch: Secrets Manager (HF token), S3 bucket, IAM roles, ECR repository, GPU and CPU compute environments, job queues, and job definitions. You can run a single full-pipeline job (download + transcribe) or two separate jobs (download to S3, then transcribe from S3).

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured (or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)
- HuggingFace token (for pyannote); never commit it

## Quick start

1. **Set the HuggingFace token** (never commit):
   ```bash
   export TF_VAR_hf_token="your_huggingface_token"
   ```

2. **Initialize and apply**:
   ```bash
   cd deploy/terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. **Note the outputs** (queue names, job definition names, bucket name). After the Docker image is pushed to ECR (e.g. by GitHub Actions), submit jobs:
   - **Full pipeline (one job):** From repo root, `./deploy/submit-job.sh "https://www.youtube.com/watch?v=VIDEO_ID"`, or use `batch_job_queue_name` and `batch_job_definition_name` with the example in `terraform output submit_job_example`.
   - **Two jobs:** From repo root, `./deploy/submit-download-job.sh "<video_url>"`, then after the download job completes, `./deploy/submit-transcribe-job.sh s3://BUCKET/jobs/<job-id>/videos`. Uses `batch_job_queue_cpu_name` / `batch_job_definition_download_name` for the first job and `batch_job_queue_name` / `batch_job_definition_transcribe_name` for the second.

**Optional – YouTube bot check:** If YouTube shows "Sign in to confirm you're not a bot", use optional cookies. See **doc/DEPLOYMENT_AWS_BATCH.md** for `YT_COOKIES_FILE`, `YT_COOKIES_S3_URI`, and `YT_COOKIES_SECRET_ARN`. You can either set `yt_cookies_secret_arn` to the ARN of an existing Secrets Manager secret containing the cookies file content, or set `yt_cookies_file_path` to a local cookies.txt path and let Terraform create the secret from that file.

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | `eu-central-1` |
| `name_prefix` | Prefix for resource names | `debate-analyzer` |
| `hf_token` | HuggingFace token (sensitive) | (required) |
| `yt_cookies_secret_arn` | ARN of Secrets Manager secret with YouTube cookies (Netscape format); optional for bot check | `null` |
| `yt_cookies_file_path` | Path to local cookies.txt (Netscape format); Terraform creates the secret from this file | `null` |
| `ecr_image_tag` | Docker image tag for job definition | `latest` |
| `batch_compute_instance_types` | GPU instance types | `["g4dn.xlarge", "g4dn.2xlarge"]` |
| `batch_min_vcpus` | Min vCPUs for GPU CE (0 = scale to zero) | `0` |
| `batch_max_vcpus` | Max vCPUs for GPU CE | `256` |
| `batch_cpu_instance_types` | CPU instance types (download job) | `["c5.xlarge"]` |
| `batch_cpu_min_vcpus` | Min vCPUs for CPU CE (0 = scale to zero) | `0` |
| `batch_cpu_max_vcpus` | Max vCPUs for CPU CE | `64` |
| `vpc_id` | VPC ID (null = default VPC) | `null` |
| `subnet_ids` | Subnet IDs (null = default VPC subnets) | `null` |
| `use_spot` | Use Spot instances | `false` |

## Outputs

- `batch_job_queue_name` – GPU queue (full pipeline and transcribe job)
- `batch_job_queue_cpu_name` – CPU queue (download job)
- `batch_job_definition_name` – full pipeline (download + transcribe)
- `batch_job_definition_download_name` – download-only (Job 1)
- `batch_job_definition_transcribe_name` – transcribe-only (Job 2)
- `s3_bucket_name` – where videos and transcripts are written
- `ecr_repository_url` – where CI pushes the image
- `output_s3_prefix_example` – example value for `OUTPUT_S3_PREFIX`
- `submit_job_example` – example `aws batch submit-job` command for full pipeline

**Submit scripts (from repo root):** `./deploy/submit-job.sh`, `./deploy/submit-download-job.sh`, `./deploy/submit-transcribe-job.sh`. See **doc/DEPLOYMENT_AWS_BATCH.md** for the two-job flow.

## Teardown

```bash
terraform destroy
```

- **ECR**: The repository is created with `force_delete = true`, so Terraform will delete all images and then the repository during destroy. No need to empty the repo manually.
- **IAM**: Destroying the Batch IAM roles requires the user running Terraform to have permission to list instance profiles for those roles. If you see `AccessDenied: ... iam:ListInstanceProfilesForRole`, add the following to the IAM user or role used for Terraform (e.g. `DatabaseAnalyzer`):

  ```json
  {
    "Effect": "Allow",
    "Action": [
      "iam:ListInstanceProfilesForRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:DeleteInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:ListAttachedRolePolicies",
      "iam:DetachRolePolicy",
      "iam:ListRolePolicies",
      "iam:DeleteRolePolicy"
    ],
    "Resource": "arn:aws:iam::*:role/debate-analyzer-*"
  }
  ```

  Alternatively, use an IAM user/role with broader IAM permissions (e.g. `IAMFullAccess` or power-user) when running `terraform destroy`.
