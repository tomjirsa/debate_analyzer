# Debate Analyzer – AWS Batch (Terraform)

This directory provisions all AWS resources for running the debate-analyzer pipeline on AWS Batch with GPU: Secrets Manager (HF token), S3 bucket, IAM roles, ECR repository, Batch compute environment, job queue, and job definition.

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

3. **Note the outputs** (queue name, job definition name, bucket name). After the Docker image is pushed to ECR (e.g. by GitHub Actions), submit a job:
   ```bash
   aws batch submit-job \
     --job-name debate-analyzer-$(date +%s) \
     --job-queue $(terraform output -raw batch_job_queue_name) \
     --job-definition $(terraform output -raw batch_job_definition_name) \
     --container-overrides '{"environment":[{"name":"VIDEO_URL","value":"https://www.youtube.com/watch?v=VIDEO_ID"},{"name":"OUTPUT_S3_PREFIX","value":"s3://BUCKET_NAME/jobs"}]}' \
     --region $(terraform output -raw aws_region 2>/dev/null || echo "eu-central-1")
   ```
   Replace `VIDEO_ID` and `BUCKET_NAME` (or use `terraform output output_s3_prefix_example`).

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | `eu-central-1` |
| `name_prefix` | Prefix for resource names | `debate-analyzer` |
| `hf_token` | HuggingFace token (sensitive) | (required) |
| `ecr_image_tag` | Docker image tag for job definition | `latest` |
| `batch_compute_instance_types` | GPU instance types | `["g4dn.xlarge"]` |
| `batch_min_vcpus` | Min vCPUs (0 = scale to zero) | `0` |
| `batch_max_vcpus` | Max vCPUs | `256` |
| `vpc_id` | VPC ID (null = default VPC) | `null` |
| `subnet_ids` | Subnet IDs (null = default VPC subnets) | `null` |
| `use_spot` | Use Spot instances | `false` |

## Outputs

- `batch_job_queue_name` – use when submitting jobs
- `batch_job_definition_name` – use when submitting jobs
- `s3_bucket_name` – where videos and transcripts are written
- `ecr_repository_url` – where CI pushes the image
- `output_s3_prefix_example` – example value for `OUTPUT_S3_PREFIX`
- `submit_job_example` – example `aws batch submit-job` command

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
