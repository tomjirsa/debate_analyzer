# Deploying Debate Analyzer to AWS Batch (GPU)

This guide describes how to run the debate-analyzer pipeline on AWS Batch with GPU: you submit a **video URL** (e.g. YouTube), and a job downloads the video in AWS, uploads it to S3, transcribes it with speaker diarization, and uploads the transcripts to S3. All infrastructure is provisioned with **Terraform**; the Docker image is built and pushed by **GitHub Actions**.

## Overview

- **Input:** Video URL (e.g. `https://www.youtube.com/watch?v=...`)
- **Output (S3):** Downloaded video and optional subtitles under `s3://<bucket>/jobs/<job-id>/videos/`; transcription JSON (and optionally audio) under `s3://<bucket>/jobs/<job-id>/transcripts/`
- **Secrets:** HuggingFace token is stored in AWS Secrets Manager and injected into the container by Batch (no code changes; set via Terraform variable).
- **Cost:** You pay only for GPU time while the job runs; the compute environment scales to zero when idle.

## 1. Terraform setup and variables

### Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.0
- AWS CLI configured (or environment variables / profile) with permissions to create the resources below
- A [HuggingFace](https://huggingface.co) account and token, with [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) terms accepted

### Variables

All provisioning is in `deploy/terraform/`. Required variable:

- **`hf_token`** – Your HuggingFace token (sensitive). Provide via:
  - `export TF_VAR_hf_token="your_token"` before `terraform apply`, or
  - A `terraform.tfvars` file (do **not** commit it), or
  - A secret backend (e.g. Vault)

Optional variables (see `deploy/terraform/variables.tf`): `aws_region`, `name_prefix`, `ecr_image_tag`, `batch_compute_instance_types`, `batch_min_vcpus`, `batch_max_vcpus`, `vpc_id`, `subnet_ids`, `use_spot`.

## 2. Terraform apply and what it creates

From the repository root:

```bash
cd deploy/terraform
terraform init
terraform plan   # review
terraform apply  # type yes when prompted
```

Terraform creates:

| Resource | Purpose |
|----------|---------|
| **Secrets Manager** secret | Stores the HuggingFace token; Batch injects it as `HF_TOKEN` into the container. |
| **S3** bucket | Holds downloaded videos and transcripts (prefix: `jobs/<job-id>/videos/` and `jobs/<job-id>/transcripts/`). |
| **IAM** roles | Job role (S3 + Secrets Manager), execution role (ECR + CloudWatch), instance role (for Batch compute EC2). |
| **ECR** repository | Holds the debate-analyzer Docker image (pushed by CI). |
| **Batch** compute environment | GPU (e.g. g4dn.xlarge), min 0 / max 256 vCPUs. |
| **Batch** job queue | Linked to the compute environment. |
| **Batch** job definition | Image, GPU, memory, `HF_TOKEN` from secret, job/execution roles, CloudWatch logs. |
| **CloudWatch** log group | Container logs from each job. |

After `apply`, note the outputs (e.g. `terraform output`): you will need **job queue name**, **job definition name**, and **bucket name** to submit jobs and find outputs.

## 3. Building and pushing the image (CI)

The Docker image is built and pushed to ECR by the **GitHub Actions** workflow `.github/workflows/build-push-ecr.yml` on push to `main` (or via `workflow_dispatch`).

### GitHub configuration

1. **AWS credentials for GitHub Actions** (choose one):
   - **OIDC (recommended):** In AWS IAM, add an OIDC identity provider for `https://token.actions.githubusercontent.com`, then create a role that trusts that provider and has ECR permissions (`GetAuthorizationToken`, `PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`). In the repo: **Settings → Secrets and variables → Actions**: add secret `AWS_ROLE_ARN` with that role’s ARN.
   - **Static credentials:** Add secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (and optionally `AWS_REGION`). Then change the workflow to use `aws-actions/configure-aws-credentials@v4` with `aws-access-key-id` / `aws-secret-access-key` instead of `role-to-assume`.

2. **Region:** Set variable **AWS_REGION** (e.g. `eu-central-1`) under **Settings → Variables** if you don’t use the default in the workflow.

3. Push to `main` (or run the workflow manually). The workflow builds the image from the repo root `Dockerfile` and pushes it to the ECR repository created by Terraform (repository name: `debate-analyzer`, tag: `latest` by default).

### Building and pushing locally

If you prefer to build and push from your machine:

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com
docker build -t <account_id>.dkr.ecr.<region>.amazonaws.com/debate-analyzer:latest .
docker push <account_id>.dkr.ecr.<region>.amazonaws.com/debate-analyzer:latest
```

Use the same region and account as Terraform; the ECR repository URL is in Terraform output `ecr_repository_url`.

## 4. Submitting a job (VIDEO_URL and OUTPUT_S3_PREFIX)

After the image is in ECR, submit a Batch job with container environment variables **VIDEO_URL** and **OUTPUT_S3_PREFIX**. The pipeline wrapper uses **AWS_BATCH_JOB_ID** (injected by Batch) to write each job’s outputs under a unique path.

Using Terraform outputs:

```bash
QUEUE=$(cd deploy/terraform && terraform output -raw batch_job_queue_name)
DEFN=$(cd deploy/terraform && terraform output -raw batch_job_definition_name)
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name)
REGION=$(cd deploy/terraform && terraform output -raw aws_region)

aws batch submit-job \
  --job-name "debate-analyzer-$(date +%s)" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"VIDEO_URL\",\"value\":\"https://www.youtube.com/watch?v=YOUR_VIDEO_ID\"},{\"name\":\"OUTPUT_S3_PREFIX\",\"value\":\"s3://$BUCKET/jobs\"}]}" \
  --region "$REGION"
```

Replace `YOUR_VIDEO_ID` with the YouTube video ID. The job will:

1. Download the video (and optional subtitles) in AWS.
2. Upload them to `s3://<bucket>/jobs/<job-id>/videos/`.
3. Transcribe with GPU and speaker diarization.
4. Upload transcription (and optionally audio) to `s3://<bucket>/jobs/<job-id>/transcripts/`.

## 5. Where downloaded videos and transcripts land in S3

- **Downloaded video and subtitles:** `s3://<bucket>/jobs/<job-id>/videos/`
- **Transcription JSON (and optionally extracted audio):** `s3://<bucket>/jobs/<job-id>/transcripts/`

`<job-id>` is the Batch job ID (e.g. from the `submit-job` output or the Batch console).

## 6. Logs and troubleshooting

- **Batch job status:** AWS Console → Batch → Jobs, or `aws batch describe-jobs --jobs <job-id> --region <region>`.
- **Container logs:** CloudWatch Logs group `/aws/batch/debate-analyzer` (or the name in Terraform output); stream prefix `batch`.
- **Failed jobs:** Check the same log group for stderr; ensure `VIDEO_URL` and `OUTPUT_S3_PREFIX` are set and the HuggingFace token is valid and has accepted the pyannote model terms.

## Summary

1. Set `TF_VAR_hf_token`, run `terraform init` and `terraform apply` in `deploy/terraform/`.
2. Configure GitHub Actions (OIDC or static AWS credentials) and push to `main` to build and push the image to ECR.
3. Submit jobs with `aws batch submit-job` and container env `VIDEO_URL` and `OUTPUT_S3_PREFIX=s3://<bucket>/jobs`.
4. Find outputs in S3 under `jobs/<job-id>/videos/` and `jobs/<job-id>/transcripts/`, and logs in CloudWatch under `/aws/batch/debate-analyzer`.
