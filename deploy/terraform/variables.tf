variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "name_prefix" {
  description = "Prefix for resource names (e.g. debate-analyzer)."
  type        = string
  default     = "debate-analyzer"
}

variable "hf_token" {
  description = "HuggingFace token for pyannote (stored in Secrets Manager). Never commit; use TF_VAR_hf_token or a secret backend."
  type        = string
  sensitive   = true
}

variable "yt_cookies_secret_arn" {
  description = "ARN of an AWS Secrets Manager secret containing the YouTube cookies file content (Netscape format). If set, the job role can read this secret and the job definition passes it as YT_COOKIES_SECRET_ARN; the entrypoint fetches the value and writes to a file before the download step."
  type        = string
  default     = null
  sensitive   = true
}

variable "yt_cookies_file_path" {
  description = "Path to a local file containing the YouTube cookies in Netscape format (e.g. from a browser extension). When set, Terraform creates a secret from this file and uses it for the Batch job. The path is relative to the working directory when running Terraform. Do not commit the file; use TF_VAR_yt_cookies_file_path or a non-committed tfvars file."
  type        = string
  default     = null
}

variable "ecr_image_tag" {
  description = "Docker image tag to use in the Batch job definition (e.g. latest)."
  type        = string
  default     = "latest"
}

variable "batch_compute_instance_types" {
  description = "EC2 instance types for the Batch compute environment (GPU)."
  type        = list(string)
  default     = ["g4dn.xlarge", "g4dn.2xlarge" ]
}

variable "batch_min_vcpus" {
  description = "Minimum vCPUs for the Batch compute environment (0 = scale to zero)."
  type        = number
  default     = 0
}

variable "batch_max_vcpus" {
  description = "Maximum vCPUs for the Batch compute environment."
  type        = number
  default     = 256
}

variable "vpc_id" {
  description = "VPC ID for the Batch compute environment. If null, default VPC is used."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Subnet IDs for the Batch compute environment. If null, default VPC subnets are used."
  type        = list(string)
  default     = null
}

variable "use_spot" {
  description = "Use Spot instances for Batch compute to reduce cost (may be interrupted)."
  type        = bool
  default     = false
}
