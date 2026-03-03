j8# 📖 AI Image API — Study Guide
## Read This Tonight Before Tomorrow's Session

---

## THE BIG PICTURE

```
User uploads image
       │
       ▼
  API SERVICE (FastAPI)
  ┌──────────────────────────┐
  │ 1. Receives image        │
  │ 2. Stores in S3          │
  │ 3. Saves record to DB    │
  │ 4. Pushes job to Redis   │
  │ 5. Returns image ID      │
  └──────────────────────────┘
       │
       │ Redis Queue
       ▼
  WORKER SERVICE (FastAPI + AI)
  ┌──────────────────────────┐
  │ 1. Picks job from Redis  │
  │ 2. Downloads from S3     │
  │ 3. Runs AI analysis      │
  │ 4. Saves result to DB    │
  │ 5. Caches in Redis       │
  └──────────────────────────┘
       │
       ▼
User calls GET /api/images/{id}
       → Gets AI analysis result
```

---

## SERVICE 1: API SERVICE (api-service/main.py)

### What It Does
The API service is the "front door" — users talk to THIS service.

### Endpoints (These Are Important for Your Dockerfile!)
```
POST /api/images/upload    → Upload image         → Port 8000
GET  /api/images/{id}      → Get result           → Port 8000
GET  /api/images           → List all images      → Port 8000
GET  /api/stats            → Processing stats     → Port 8000
GET  /health               → Liveness probe       → Port 8000
GET  /ready                → Readiness probe      → Port 8000
GET  /docs                 → Swagger UI           → Port 8000
```

### What It Connects To (You Need This for Kubernetes!)
```
PostgreSQL  → DATABASE_URL env var     → Port 5432
Redis       → REDIS_HOST env var       → Port 6379
S3          → S3_BUCKET env var        → Via AWS SDK (IRSA)
```

### Libraries (You Need This for Dockerfile!)
```
fastapi      → Web framework
uvicorn      → ASGI server (runs FastAPI)
asyncpg      → PostgreSQL async driver
redis        → Redis client
boto3        → AWS SDK (for S3)
python-multipart → File upload handling
```

---

## SERVICE 2: WORKER SERVICE (worker-service/main.py)

### What It Does
The worker is a BACKGROUND PROCESSOR — it doesn't serve users directly.
It watches the Redis queue and processes images when jobs appear.

### Endpoints (Only Health Checks!)
```
GET /health    → Liveness probe     → Port 8001
GET /ready     → Readiness probe    → Port 8001
```

### What It Connects To
```
PostgreSQL  → DATABASE_URL env var     → Port 5432
Redis       → REDIS_HOST env var       → Port 6379
S3          → S3_BUCKET env var        → Via AWS SDK (IRSA)
```

### Libraries
```
fastapi      → Only for health check endpoints
uvicorn      → Runs the health check server
psycopg2     → PostgreSQL sync driver (different from api-service!)
redis        → Redis client
boto3        → AWS SDK (for S3)
Pillow       → Image processing (AI analysis)
```

### The AI Part
```
The analyze_image() function does:
  1. Opens the image with Pillow
  2. Extracts: dimensions, format, color mode, file size
  3. Analyzes: dominant colors, brightness, orientation
  4. Classifies: quality level, color tone
  5. Generates: tags and confidence score

In a REAL production system, you'd replace this with:
  - AWS Rekognition (object detection)
  - TensorFlow model (custom ML)
  - OpenAI Vision API
  
But for our demo, Pillow analysis is enough.
The DEPLOYMENT is what matters, not the AI model!
```

---

## WHAT YOU NEED TO KNOW FOR TOMORROW

You DON'T need to understand every line of Python code.

You DO need to know:

### 1. Ports (For Dockerfile and Service YAML)
```
API Service:    Port 8000
Worker Service: Port 8001
PostgreSQL:     Port 5432
Redis:          Port 6379
```

### 2. Environment Variables (For deployment.yaml)
```
Both services need:
  DATABASE_URL    → Connection string to PostgreSQL
  REDIS_HOST      → Redis hostname
  REDIS_PORT      → Redis port (6379)
  S3_BUCKET       → S3 bucket name
  AWS_REGION      → us-east-1
  ENVIRONMENT     → dev/staging/prod
  APP_VERSION     → 1.0.0
```

### 3. Health Check Paths (For liveness/readiness probes)
```
API Service:
  Liveness:  GET /health  on port 8000
  Readiness: GET /ready   on port 8000

Worker Service:
  Liveness:  GET /health  on port 8001
  Readiness: GET /ready   on port 8001
```

### 4. How to Start Each Service (For Dockerfile CMD)
```
API Service:
  uvicorn main:app --host 0.0.0.0 --port 8000

Worker Service:
  uvicorn main:app --host 0.0.0.0 --port 8001
```

### 5. Python Version and Base Image
```
Both services use Python 3.12
Base image: python:3.12-slim
```

### 6. The Flow (For Architecture Understanding)
```
Upload:   User → API (port 8000) → S3 + PostgreSQL + Redis Queue
Process:  Worker polls Redis → Downloads from S3 → AI Analysis → PostgreSQL
Retrieve: User → API (port 8000) → Redis Cache or PostgreSQL
```

---

## TOMORROW'S TASKS — WHAT YOU'LL WRITE

```
TASK 1: Dockerfile for API Service
  Hints: Python base image, install requirements, copy code, 
         expose port 8000, run uvicorn

TASK 2: Dockerfile for Worker Service
  Hints: Same pattern but port 8001, different requirements

TASK 3: Kubernetes Manifests
  - deployment.yaml for API Service (with env vars, probes)
  - deployment.yaml for Worker Service
  - service.yaml for API Service
  - service.yaml for Worker Service
  - PostgreSQL deployment + service
  - Redis deployment + service

TASK 4: Helm Chart
  - values.yaml with all configurable values
  - Templates for all the above

TASK 5: Terraform
  - VPC, EKS, S3 bucket, RDS, ElastiCache, ALB Controller

TASK 6: GitHub Actions
  - CI/CD pipeline for both services
```

---

## STUDY THESE TONIGHT

Focus on memorizing:
  ✅ The 2 ports: 8000 (API) and 8001 (Worker)
  ✅ The 6 environment variables both services need
  ✅ The health check paths: /health and /ready
  ✅ The architecture flow: User → API → S3/Redis/DB → Worker → DB
  ✅ Both services use Python 3.12 and uvicorn

That's ALL you need to know to write the DevOps files tomorrow! 🚀
