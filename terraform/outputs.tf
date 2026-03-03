# ── Cluster Info ──
output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.main.name}"
}

# ── ECR Info ──
output "ecr_api_url" {
  description = "ECR repository URL for API service"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_worker_url" {
  description = "ECR repository URL for Worker service"
  value       = aws_ecr_repository.worker.repository_url
}

output "ecr_login_command" {
  description = "Command to login to ECR"
  value       = "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

# ── Database Info ──
output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "database_url" {
  description = "Full DATABASE_URL for the application"
  value       = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${var.db_name}"
  sensitive   = true
}

# ── Redis Info ──
output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

# ── S3 Info ──
output "s3_bucket_name" {
  description = "S3 bucket name for image storage"
  value       = aws_s3_bucket.images.id
}

# ── ALB Controller ──
output "alb_controller_role_arn" {
  description = "IAM role ARN for ALB Controller"
  value       = aws_iam_role.alb_controller.arn
}

# ── App Pod Role ──
output "app_pod_role_arn" {
  description = "IAM role ARN for app pods (S3 access)"
  value       = aws_iam_role.app_pod.arn
}

# ── VPC Info ──
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}