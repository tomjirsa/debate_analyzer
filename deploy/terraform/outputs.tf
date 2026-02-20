output "aws_region" {
  description = "AWS region used for resources."
  value       = local.region
}

output "ecr_repository_url" {
  description = "ECR repository URL (push image here; tag with ecr_image_tag)."
  value       = aws_ecr_repository.this.repository_url
}

output "ecr_image_uri" {
  description = "Full ECR image URI used by the Batch job definition."
  value       = local.ecr_image
}

output "s3_bucket_name" {
  description = "S3 bucket for downloaded videos and transcripts."
  value       = aws_s3_bucket.output.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 output bucket."
  value       = aws_s3_bucket.output.arn
}

output "batch_job_queue_name" {
  description = "Name of the Batch job queue (use when submitting jobs)."
  value       = aws_batch_job_queue.this.name
}

output "batch_job_queue_arn" {
  description = "ARN of the Batch job queue."
  value       = aws_batch_job_queue.this.arn
}

output "batch_job_definition_name" {
  description = "Name of the Batch job definition (full pipeline; use when submitting jobs)."
  value       = aws_batch_job_definition.this.name
}

output "batch_job_definition_arn" {
  description = "ARN of the Batch job definition (revision is appended at runtime)."
  value       = aws_batch_job_definition.this.arn
}

output "batch_job_queue_cpu_name" {
  description = "Name of the CPU job queue (for download and stats jobs; CPU-only)."
  value       = aws_batch_job_queue.cpu.name
}

output "batch_job_definition_download_name" {
  description = "Name of the download-only job definition (Job 1)."
  value       = aws_batch_job_definition.download.name
}

output "batch_job_definition_transcribe_name" {
  description = "Name of the transcribe-only job definition (Job 2)."
  value       = aws_batch_job_definition.transcribe.name
}

output "batch_job_definition_stats_name" {
  description = "Name of the stats job definition (Job 3; run after transcribe)."
  value       = aws_batch_job_definition.stats.name
}

output "output_s3_prefix_example" {
  description = "Example OUTPUT_S3_PREFIX for container env (use with VIDEO_URL when submitting job)."
  value       = "s3://${aws_s3_bucket.output.id}/jobs"
}

output "submit_job_example" {
  description = "Example: submit a Batch job (replace VIDEO_URL)."
  value       = "aws batch submit-job --job-name debate-analyzer-$(date +%s) --job-queue ${aws_batch_job_queue.this.name} --job-definition ${aws_batch_job_definition.this.name} --container-overrides '{\"environment\":[{\"name\":\"VIDEO_URL\",\"value\":\"https://www.youtube.com/watch?v=VIDEO_ID\"},{\"name\":\"OUTPUT_S3_PREFIX\",\"value\":\"s3://${aws_s3_bucket.output.id}/jobs\"}]}' --region ${local.region}"
}
