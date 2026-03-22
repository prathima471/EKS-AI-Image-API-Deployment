# ── ElastiCache Subnet Group ──
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.cluster_name}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id               # Private subnets only!
}

# ── ElastiCache Security Group ──
# "Only allow traffic from EKS nodes on port 6379"
resource "aws_security_group" "redis" {
  name        = "${local.cluster_name}-redis-sg"
  description = "Allow Redis access from EKS nodes"
  vpc_id      = aws_vpc.main.id

  # Allow Redis from private subnets 
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.private_subnet_cidrs
    description = "Redis from EKS nodes"
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.cluster_name}-redis-sg"
  }
}

# ── ElastiCache Redis Cluster ──
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.cluster_name}-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.redis_node_type           # cache.t3.micro
  num_cache_nodes      = 1                              # Single node for dev
  port                 = 6379

  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = {
    Name = "${local.cluster_name}-redis"
  }
}
