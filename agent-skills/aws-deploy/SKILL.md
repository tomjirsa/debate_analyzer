---

## name: aws-deploy

description: Guides deploying the Debate Analyzer to AWS (Batch and Web app Terraform stacks, job submission, RDS migrations). Use when the user asks to deploy to AWS, run terraform apply for the batch or webapp stack, submit Batch jobs (transcribe, postprocess, LLM analysis), run terraform batch job, or follow deploy notes.

# AWS Deploy

## When to use

Apply this skill when the user asks to deploy to AWS, run Terraform (apply/destroy/plan) for the batch or web app stack, submit AWS Batch jobs (transcribe, postprocess, LLM analysis), update DB schema on RDS, or follow steps from deploy notes.

## Secrets (mandatory)

- **Never** add or suggest putting secrets (passwords, tokens, paths to cookies) into the repo or into `deploy/deployNotes.txt`. Do not edit deployNotes.txt (project rule).
- Required values must be provided by **sourcing the local secrets script** or by setting **TF_VAR_*** or a **local, non-committed** `terraform.tfvars`.
- **Preferred:** Copy `deploy/set-deploy-secrets.sh.example` to `deploy/set-deploy-secrets.sh`, fill in secrets, then run `source deploy/set-deploy-secrets.sh` (from repo root) before any `terraform` or submit-job commands. The file `set-deploy-secrets.sh` is gitignored and must never be committed.

## Intent → Action mapping


| User intent (examples)                                                   | Agent action                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "Apply batch stack", "terraform apply batch stack", "deploy batch stack" | Ensure deploy secrets are loaded `[ -n "${TF_VAR_hf_token}" ] && echo "Batch Terraform env OK (hf_token set)"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| "Apply web app stack", "terraform apply webapp"                          | Same for secrets; then `cd deploy/terraform-webapp && terraform apply`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| "Run batch job", "submit batch job", "run terraform batch job"           | Treat as "submit an AWS Batch job". **By default, list jobs available in S3 first:** from `deploy/terraform/` get the bucket name (`terraform output -raw s3_bucket_name`), run `aws s3api list-objects-v2 --bucket BUCKET --prefix "jobs/" --delimiter "/" --query 'CommonPrefixes[*].Prefix'`; display the list to user and let the user pick one. Then determine **job type** (transcribe / postprocess / LLM analysis) and **S3 URI**. If the user already provided job ID and type, listing can be skipped. Run from `deploy/scripts/submit-jobs/`: `./submit-transcribe-job.sh s3://bucket/jobs/<id>/videos/`, `./submit-transcript-postprocess-job.sh s3://bucket/jobs/<id>/transcripts/`, or `./submit-llm-analysis-job.sh s3://bucket/jobs/<id>/transcripts/`. Scripts read bucket/queue from Terraform outputs in `deploy/terraform/`.
| "Destroy batch stack", "terraform destroy batch"                         | Ensure deploy secrets are loaded (e.g. `TF_VAR_hf_token` set via `source deploy/set-deploy-secrets.sh`). From repo root: `cd deploy/terraform && terraform destroy` (use `-auto-approve` only if user asked to destroy without confirmation). After Terraform finishes, force-delete Secrets Manager secrets: `aws secretsmanager delete-secret --secret-id "debate-analyzer/huggingface-token" --force-delete-without-recovery --region <region>`; if the batch stack was created with `yt_cookies_file_path`, also `aws secretsmanager delete-secret --secret-id "debate-analyzer/yt-cookies" --force-delete-without-recovery --region <region>`. Region: `eu-central-1` or `terraform output -raw aws_region` from `deploy/terraform/` before destroy.
| "Destroy web app stack", "terraform destroy webapp"                      | Ensure web app vars are set (`TF_VAR_existing_s3_bucket_name`, `TF_VAR_admin_username`, `TF_VAR_admin_password`, `TF_VAR_db_password`), e.g. via `source deploy/set-deploy-secrets.sh`. From repo root: `cd deploy/terraform-webapp && terraform destroy`. After Terraform finishes, force-delete the app secret: `aws secretsmanager delete-secret --secret-id "debate-analyzer-webapp/app-secrets" --force-delete-without-recovery --region <region>` (e.g. `eu-central-1` or `terraform output -raw aws_region` from that stack if available). |
|                                                                          |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |


## Batch stack (`deploy/terraform/`)

- **Required:** `hf_token`. Optional: `yt_cookies_file_path`, `enable_cloudfront`, etc.
- **Commands:** `terraform init` / `plan` / `apply` from `deploy/terraform/`; list jobs via `aws s3api list-objects-v2` (bucket/prefix from Terraform outputs or deploy notes).
- **Destroy:** `terraform destroy` from `deploy/terraform/`; then force-delete secrets `debate-analyzer/huggingface-token` and, if used, `debate-analyzer/yt-cookies` with `aws secretsmanager delete-secret --secret-id <secret-id> --force-delete-without-recovery --region <region>`.
- **Submit jobs:** By default, list jobs in S3 first (`aws s3api list-objects-v2 --bucket BUCKET --prefix "jobs/" --delimiter "/" --query 'CommonPrefixes[*].Prefix'`; bucket from `terraform output -raw s3_bucket_name` in `deploy/terraform/`). Then run `./submit-transcribe-job.sh`, `./submit-transcript-postprocess-job.sh`, or `./submit-llm-analysis-job.sh` with the appropriate S3 URI (e.g. `s3://bucket/jobs/<job-id>/videos/` or `.../transcripts/`). Run from `deploy/scripts/submit-jobs/`; scripts resolve Terraform outputs from `deploy/terraform/`.

## Web app stack (`deploy/terraform-webapp/`)

- **Required:** `existing_s3_bucket_name`, `admin_username`, `admin_password`, `db_password`. Optional: `rds_publicly_accessible`, `rds_allowed_cidr_blocks` for migrations.
- **Commands:** `terraform init` / `plan` / `apply` or `destroy` from `deploy/terraform-webapp/`. After destroy, run `aws secretsmanager delete-secret --secret-id "debate-analyzer-webapp/app-secrets" --force-delete-without-recovery --region <region>`.

## Destroy (both stacks)

- **ECR and S3:** It is acceptable if ECR (repositories/images) and the S3 bucket are not destroyed during destroy (e.g. due to policies, non-empty bucket, or manual retention). Treat destroy as successful once Terraform completes and the Secrets Manager secrets are force-deleted; do not fail or retry if ECR/S3 remain.
- **Secret IDs:** If `name_prefix` was overridden (batch default `debate-analyzer`, web app default `debate-analyzer-webapp`), secret IDs change accordingly (e.g. `"<name_prefix>/huggingface-token"`, `"<name_prefix>/app-secrets"`). Use the appropriate secret ID when force-deleting.

## DB schema updates

Temporarily set `rds_publicly_accessible=true` and `rds_allowed_cidr_blocks=[...]`, apply, set `DATABASE_URL`, run `poetry run alembic upgrade head` from repo root, then set RDS back to private and apply again.

## References

- [doc/AWS_SETUP.md](../../doc/AWS_SETUP.md) — step-by-step AWS setup and variable descriptions.
- [doc/DEPLOYMENT_AWS_BATCH.md](../../doc/DEPLOYMENT_AWS_BATCH.md) — job submission and two-job flow.
- [deploy/terraform/README.md](../../deploy/terraform/README.md), [deploy/terraform-webapp/README.md](../../deploy/terraform-webapp/README.md) — Terraform usage.

## What this skill does not do

- It does not modify or generate content for `deploy/deployNotes.txt` (per rule).
- It does not implement new Terraform resources; it guides usage of existing stacks and scripts.

