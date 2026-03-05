# ── GitHub OIDC Provider ──
# "Allow GitHub Actions to authenticate to AWS"
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# ── GitHub Actions Role ──
# "What permissions does GitHub Actions have?"
resource "aws_iam_role" "github_actions" {
  name = "${local.cluster_name}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:prathima471/EKS-AI-Image-API-Deployment:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

# Give GitHub Actions these permissions:
# ECR (push images), EKS (deploy), S3 (app needs it)
resource "aws_iam_role_policy_attachment" "github_ecr" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
  role       = aws_iam_role.github_actions.name
}

resource "aws_iam_role_policy_attachment" "github_eks" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.github_actions.name
}

# Output the ARN (this is your secret!)
output "github_actions_role_arn" {
  description = "Add this as AWS_ROLE_ARN secret in GitHub"
  value       = aws_iam_role.github_actions.arn
}