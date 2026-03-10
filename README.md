# EKS AI Image API Deployment

End-to-end deployment of a microservices-based AI image processing API on Amazon EKS. Built to demonstrate production-grade DevOps practices including infrastructure-as-code, container orchestration, CI/CD automation, and GitOps.

## What This Project Does

This platform lets users upload images through a REST API, which are then analyzed by an AI worker service. The API service handles uploads, stores images in S3, and queues processing jobs via Redis. A separate worker service picks up jobs, runs image analysis (dimensions, color profiling, orientation detection), and stores results in PostgreSQL.

I built this to practice the full DevOps lifecycle — writing Dockerfiles, Kubernetes manifests, Helm charts, Terraform infrastructure, and CI/CD pipelines from scratch.

---

## Architecture

```
User
  └── POST /api/images/upload
        │
        ├── FastAPI (API Service)
        │     ├── Store image → S3
        │     ├── Save metadata → PostgreSQL (RDS)
        │     └── Push job → Redis (ElastiCache)
        │
        └── FastAPI (Worker Service)
              ├── Poll Redis for jobs
              ├── Download image from S3
              ├── Run AI analysis (Pillow)
              └── Save results → PostgreSQL
```

```
CI/CD + GitOps Flow:

  Push to main
      │
      ├── GitHub Actions
      │     ├── Lint & test
      │     ├── Build Docker images
      │     ├── Scan with Trivy
      │     ├── Push to ECR
      │     └── Update values.yaml with new image tag
      │
      └── ArgoCD (watching the repo)
            └── Detects values.yaml change → deploys to EKS
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Application | Python 3.11, FastAPI, Uvicorn |
| Containers | Docker, AWS ECR |
| Orchestration | Kubernetes 1.29 (EKS), Helm |
| Infrastructure | Terraform (AWS provider ~5.0) |
| Database | PostgreSQL 15 on RDS |
| Cache / Queue | Redis 7.0 on ElastiCache |
| Storage | AWS S3 |
| Load Balancer | AWS ALB (via Ingress Controller) |
| GitOps | ArgoCD |
| CI/CD | GitHub Actions |
| Security Scanning | Trivy |

---

## Project Structure

```
.
├── .github/workflows/
│   └── deploy.yaml               # CI/CD pipeline
│
├── ai-image-project/
│   ├── api-service/
│   │   ├── main.py               # FastAPI app (image upload & retrieval)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── worker-service/
│   │   ├── main.py               # Background worker (image analysis)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── k8-manifests/             # Raw K8s manifests (manual deploy reference)
│   │   ├── api-deployment.yaml
│   │   ├── api-service.yaml
│   │   ├── api-hpa.yaml
│   │   ├── worker-deployment.yaml
│   │   ├── worker-service.yaml
│   │   ├── worker-hpa.yaml
│   │   ├── redis-deployment.yaml
│   │   ├── redis-service.yaml
│   │   ├── postgres-deployment.yaml
│   │   ├── postgres-service.yaml
│   │   └── ingress.yaml
│   │
│   └── helm-chart/
│       ├── Chart.yaml
│       ├── values.yaml           # Image tags, resource limits, config
│       └── templates/            # Deployments, services, ingress, HPA
│
├── terraform/
│   ├── vpc.tf                    # VPC, subnets, NAT gateway
│   ├── eks.tf                    # EKS cluster and node group
│   ├── rds.tf                    # PostgreSQL on RDS
│   ├── elasticcache.tf           # Redis on ElastiCache
│   ├── ecr.tf                    # Container registries
│   ├── s3.tf                     # Image storage bucket
│   ├── iam.tf                    # IAM roles, IRSA, OIDC
│   ├── alb.tf                    # ALB Ingress Controller permissions
│   ├── github-oidc.tf            # GitHub Actions OIDC (no stored secrets)
│   └── dev.tfvars                # Dev environment variable values
│
└── argocd/
    └── ai-image-application.yaml  # ArgoCD Application definition
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/images/upload` | Upload an image for processing |
| GET | `/api/images/{id}` | Get analysis result by ID |
| GET | `/api/images` | List all uploaded images |
| GET | `/api/stats` | Processing statistics |
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |
| GET | `/docs` | Swagger UI |

---

## Infrastructure Overview

### Networking

The VPC is split into public and private subnets across 3 availability zones. EKS nodes, RDS, and ElastiCache all sit in private subnets — they can't be reached from the internet directly. The ALB lives in the public subnets and handles incoming traffic. A NAT Gateway gives the private resources outbound internet access when they need it.

### EKS Cluster

- Kubernetes 1.29, two `t3.micro` nodes (dev sizing)
- Nodes run in private subnets
- Public API endpoint enabled so you can use `kubectl` from outside
- OIDC provider enabled for IRSA — pods assume IAM roles without needing hardcoded credentials

### Databases

- **RDS PostgreSQL 15** — `db.t3.micro`, 20GB storage with auto-expand to 50GB, private subnet only
- **ElastiCache Redis 7.0** — `cache.t3.micro`, single node, private subnet only

### ECR

Two repositories (`api-service` and `worker-service`). Scan on push is enabled. Lifecycle policy keeps the last 10 images.

### S3

Private bucket with public access blocked, AES256 encryption, and versioning enabled.

---

## Raw Kubernetes Manifests

Before moving to Helm, I wrote plain Kubernetes manifests for every resource in `ai-image-project/k8-manifests/`. These cover the same workloads as the Helm chart — API, worker, Redis, PostgreSQL, ingress, and HPAs — but as static YAML files with no templating.

They're kept in the repo as a reference and for manual testing:

```bash
kubectl apply -f ai-image-project/k8-manifests/
```

The Helm chart was built on top of these, converting hardcoded values into `{{ .Values.* }}` references and adding environment-specific configuration. In production (GitOps), ArgoCD renders the Helm chart and manages the cluster state — the raw manifests are not applied directly.

---

## CI/CD Pipeline

The GitHub Actions workflow in `.github/workflows/deploy.yaml` runs on every push to main.

**Job 1 — Test**: Installs dependencies for both services, lints with flake8.

**Job 2 — Build & Push**: Builds Docker images tagged with the git short SHA, scans them with Trivy, pushes to ECR. Uses GitHub OIDC to authenticate with AWS — no access keys stored in secrets.

**Job 3 — Update Helm Values**: Uses `yq` to update the image tags in `values.yaml` and commits that back to the repo. This is what triggers ArgoCD.

The pipeline previously had a fourth job that ran `helm upgrade --install` directly from CI — authenticating to EKS and deploying in-pipeline. That job is still in the workflow file but commented out. It was replaced by the GitOps approach: CI only updates `values.yaml`, and ArgoCD owns the actual deployment. This decouples image delivery from cluster state management and gives ArgoCD full control over drift detection and self-healing.

---

## GitOps with ArgoCD

ArgoCD watches the main branch of this repo. When it sees a change to the Helm chart (specifically values.yaml), it automatically syncs the cluster to match. `prune: true` removes resources that no longer exist in git. `selfHeal: true` corrects any manual changes made directly to the cluster.

The workflow is: push code → CI builds image → CI updates values.yaml → ArgoCD deploys. No manual `helm upgrade` commands needed.

---

## Deploying from Scratch

### Prerequisites

- AWS CLI configured
- Terraform >= 1.5.0
- kubectl
- Helm 3
- ArgoCD CLI (optional)

### 1. Provision Infrastructure

```bash
cd terraform
terraform init
terraform apply -var-file="dev.tfvars"
```

This creates the VPC, EKS cluster, RDS, ElastiCache, ECR repos, S3 bucket, and all IAM roles.

### 2. Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name eks-ai-image-dev
```

### 3. Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 4. Deploy the ArgoCD Application

```bash
kubectl apply -f argocd/ai-image-application.yaml
```

ArgoCD will pull the Helm chart from the repo and deploy it to the cluster.

### 5. Push Code to Trigger CI/CD

From here, pushing any code change to main kicks off the full pipeline — tests, build, push, and deploy.

---

## Monitoring

The Helm chart includes Prometheus and Grafana configuration for cluster and application observability — scraping metrics from both services and visualizing them via pre-built dashboards.

**However, this is commented out in `values.yaml` and not deployed by default.** The dev cluster runs two `t3.micro` nodes (1 vCPU / 1GB RAM each). The Prometheus stack alone (Prometheus, Alertmanager, Grafana, kube-state-metrics, node-exporter) consumes enough memory to push the nodes into resource pressure, causing pod evictions and OOMKill events for the actual application workloads.

To enable monitoring on a cluster with adequate resources (e.g. `t3.small` or larger):

```yaml
# values.yaml
monitoring:
  enabled: true  # set to false by default due to t3.micro resource constraints

  prometheus:
    retention: 7d
    resources:
      requests:
        memory: 512Mi
        cpu: 250m

  grafana:
    adminPassword: your-password
    resources:
      requests:
        memory: 256Mi
        cpu: 100m
```

What would be tracked once enabled:
- HTTP request rate, latency, and error rate per endpoint
- Worker job queue depth and processing throughput
- Pod CPU and memory usage
- Node-level resource utilization

---

## Scaling

The Helm chart includes Horizontal Pod Autoscalers for both services (disabled by default to save resources in dev). To enable them, update `values.yaml`:

```yaml
api:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

worker:
  autoscaling:
    enabled: true
    minReplicas: 1
    maxReplicas: 8
    targetCPUUtilizationPercentage: 60
```

---

## Security Notes

- EKS nodes, RDS, and ElastiCache are in private subnets with no public access
- Containers run as non-root users
- ECR images are scanned on push with Trivy
- GitHub Actions uses OIDC to assume an IAM role — no long-lived credentials stored anywhere
- Pods use IRSA (IAM Roles for Service Accounts) to access S3 — no credentials in environment variables
- The database password in `terraform/rds.tf` is hardcoded for dev simplicity — use AWS Secrets Manager for anything beyond that

---

## Local Development

You can run both services locally with Docker Compose or just Python directly. You'll need local PostgreSQL and Redis running, and AWS credentials configured for S3 access.

```bash
cd ai-image-project/api-service
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd ai-image-project/worker-service
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Set the required environment variables before starting:

```
DATABASE_URL=postgresql://postgres:postgres123!@localhost:5432/imagedb
REDIS_HOST=localhost
REDIS_PORT=6379
S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```
