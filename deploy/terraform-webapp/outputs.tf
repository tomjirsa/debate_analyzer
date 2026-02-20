output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = aws_lb.app.dns_name
}

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port) for DATABASE_URL."
  value       = aws_db_instance.app.endpoint
}

output "ecr_repository_url" {
  description = "ECR repository URL for the web app Docker image."
  value       = aws_ecr_repository.app.repository_url
}

output "web_url" {
  description = "URL to access the web app (HTTP; add CNAME or use ALB DNS)."
  value       = "http://${aws_lb.app.dns_name}"
}
