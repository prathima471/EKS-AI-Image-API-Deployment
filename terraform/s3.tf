# ── S3 Bucket (Image Storage) ──
# API uploads images here, Worker downloads from here
resource "aws_s3_bucket" "images" {
  bucket        = "${local.cluster_name}-images-${data.aws_caller_identity.current.account_id}"
  force_delete  = true                     # Allows terraform destroy with objects inside

  tags = {
    Name = "${local.cluster_name}-images"
  }
}

# Get current AWS account ID (used to make bucket name unique)
data "aws_caller_identity" "current" {}

# Block all public access (images are private!)
resource "aws_s3_bucket_public_access_block" "images" {
  bucket = aws_s3_bucket.images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable server-side encryption (security best practice)
resource "aws_s3_bucket_server_side_encryption_configuration" "images" {
  bucket = aws_s3_bucket.images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Enable versioning (recover accidentally deleted images)
resource "aws_s3_bucket_versioning" "images" {
  bucket = aws_s3_bucket.images.id

  versioning_configuration {
    status = "Enabled"
  }
}