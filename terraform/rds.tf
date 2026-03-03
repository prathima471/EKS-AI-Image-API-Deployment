# ── RDS Subnet Group ──
# "Put the database in private subnets (secure!)"
resource "aws_db_subnet_group" "main" {
  name       = "${local.cluster_name}-db-subnet"
  subnet_ids = aws_subnet.private[*].id               # Private subnets only!

  tags = {
    Name = "${local.cluster_name}-db-subnet"
  }
}

# ── RDS Security Group ──
# "Only allow traffic from EKS nodes on port 5432"
resource "aws_security_group" "rds" {
  name        = "${local.cluster_name}-rds-sg"
  description = "Allow PostgreSQL access from EKS nodes"
  vpc_id      = aws_vpc.main.id

  # Allow PostgreSQL from private subnets (where EKS nodes are)
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.private_subnet_cidrs             # Only from private subnets
    description = "PostgreSQL from EKS nodes"
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.cluster_name}-rds-sg"
  }
}

# ── RDS PostgreSQL Instance ──
resource "aws_db_instance" "postgres" {
  identifier     = "${local.cluster_name}-postgres"
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.db_instance_class               # db.t3.micro

  allocated_storage     = 20                            # 20GB storage
  max_allocated_storage = 50                            # Auto-expand up to 50GB

  db_name  = var.db_name                                # "imagedb"
  username = var.db_username                            # "postgres"
  password = var.db_password                            # "postgres123!"

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = false                           # Single AZ for dev (cheaper)
  publicly_accessible = false                           # NOT accessible from internet!
  skip_final_snapshot = true                            # Skip backup on destroy (dev only)

  tags = {
    Name = "${local.cluster_name}-postgres"
  }
}