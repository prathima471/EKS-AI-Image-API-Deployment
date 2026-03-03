# ── ECR Repository for API Service ──
resource "aws_ecr_repository" "api" {
  name                 = "${local.cluster_name}/api-service"
  image_tag_mutability = "MUTABLE"
  force_delete         = true       # Allows terraform destroy even with images

  image_scanning_configuration {
    scan_on_push = true              # Scan for vulnerabilities on every push
  }

  tags = {
    Name    = "${local.cluster_name}-api-ecr"
    Service = "api"
  }
}

# ── ECR Repository for Worker Service ──
resource "aws_ecr_repository" "worker" {
  name                 = "${local.cluster_name}/worker-service"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name    = "${local.cluster_name}-worker-ecr"
    Service = "worker"
  }
}

# ── Lifecycle Policy (keep only last 10 images) ──
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}
