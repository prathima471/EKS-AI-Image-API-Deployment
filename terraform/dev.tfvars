aws_region         = "us-east-1"
project_name       = "eks-ai-image"
environment        = "dev"

# VPC
vpc_cidr             = "10.0.0.0/16"
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]

# EKS
cluster_version    = "1.29"
node_instance_type = "t3.micro"
node_desired_size  = 2
node_min_size      = 1
node_max_size      = 3

# RDS PostgreSQL
db_instance_class = "db.t3.micro"
db_name           = "imagedb"
db_username       = "postgres"
db_password       = "postgres123!"

# ElastiCache Redis
redis_node_type = "cache.t3.micro"