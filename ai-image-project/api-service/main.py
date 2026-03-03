"""
AI Image API Service — Handles image uploads, retrieval, and results.
=====================================================================
This is the FRONTEND service that users interact with.

ENDPOINTS:
  POST /api/images/upload     → Upload an image for AI processing
  GET  /api/images/{id}       → Get processing result for an image
  GET  /api/images            → List all processed images
  GET  /health                → Liveness probe
  GET  /ready                 → Readiness probe
  GET  /docs                  → Swagger UI (auto-generated)

ARCHITECTURE:
  User uploads image → API stores in S3 → Pushes job to Redis queue
  Worker picks up job → Runs AI model → Saves result to PostgreSQL
  User calls GET → API reads result from PostgreSQL
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
79j
import boto3
import redis
import asyncpg
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

# ── Configuration from Environment Variables ──
# These will be injected by Kubernetes (deployment.yaml env section)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/imagedb")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
S3_BUCKET = os.getenv("S3_BUCKET", "ai-image-bucket")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ── Logging ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Global connections (initialized on startup) ──
db_pool = None
redis_client = None
s3_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, Redis, and S3 connections on startup."""
    global db_pool, redis_client, s3_client

    logger.info("Starting AI Image API Service...")

    # Connect to PostgreSQL
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        # Create table if not exists
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id UUID PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    s3_key VARCHAR(500) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    result JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    processed_at TIMESTAMP
                )
            """)
        logger.info("PostgreSQL connected and table ready")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        db_pool = None

    # Connect to Redis
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        redis_client = None

    # Connect to S3
    try:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        logger.info("S3 client initialized")
    except Exception as e:
        logger.error(f"S3 client failed: {e}")
        s3_client = None

    yield  # App runs here

    # Cleanup on shutdown
    if db_pool:
        await db_pool.close()
    logger.info("AI Image API Service stopped")


# ── FastAPI App ──
app = FastAPI(
    title="AI Image Processing API",
    description="Upload images for AI-powered analysis — object detection, classification, and metadata extraction",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ── Health Check Endpoints (Kubernetes probes call these) ──

@app.get("/health", tags=["Health"])
async def health():
    """Liveness probe — is the app process alive?"""
    return {"status": "healthy", "service": "api", "version": APP_VERSION}


@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness probe — can this pod serve traffic?"""
    checks = {
        "database": db_pool is not None,
        "redis": False,
        "s3": s3_client is not None,
    }

    # Check Redis
    try:
        if redis_client:
            redis_client.ping()
            checks["redis"] = True
    except Exception:
        checks["redis"] = False

    all_ready = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ready else 503,
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
    )


# ── API Endpoints ──

@app.post("/api/images/upload", tags=["Images"])
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image for AI processing.

    Flow:
      1. Generate unique ID
      2. Upload image to S3
      3. Save record to PostgreSQL (status: pending)
      4. Push job to Redis queue (worker picks it up)
      5. Return image ID (user polls for result)
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_id = uuid.uuid4()
    s3_key = f"uploads/{image_id}/{file.filename}"

    try:
        # 1. Upload to S3
        contents = await file.read()
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=contents,
            ContentType=file.content_type,
        )
        logger.info(f"Uploaded {file.filename} to S3: {s3_key}")

        # 2. Save to database
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO images (id, filename, s3_key, status) VALUES ($1, $2, $3, $4)",
                image_id, file.filename, s3_key, "pending",
            )

        # 3. Push job to Redis queue
        job = json.dumps({"image_id": str(image_id), "s3_key": s3_key, "filename": file.filename})
        redis_client.lpush("image_processing_queue", job)
        logger.info(f"Job queued for image {image_id}")

        return {
            "image_id": str(image_id),
            "filename": file.filename,
            "status": "pending",
            "message": "Image uploaded successfully. Processing will begin shortly.",
        }

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/images/{image_id}", tags=["Images"])
async def get_image(image_id: str):
    """
    Get processing result for an image.

    Users poll this endpoint after uploading.
    Status flow: pending → processing → completed/failed
    """
    # Check Redis cache first (fast!)
    cached = redis_client.get(f"result:{image_id}") if redis_client else None
    if cached:
        return json.loads(cached)

    # Not in cache — check database
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM images WHERE id = $1", uuid.UUID(image_id))

    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

    result = {
        "image_id": str(row["id"]),
        "filename": row["filename"],
        "status": row["status"],
        "result": row["result"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
    }

    # Cache completed results in Redis (expire after 1 hour)
    if row["status"] == "completed" and redis_client:
        redis_client.setex(f"result:{image_id}", 3600, json.dumps(result))

    return result


@app.get("/api/images", tags=["Images"])
async def list_images(limit: int = 20, status: str = None):
    """
    List all processed images.

    Optional filter by status: pending, processing, completed, failed
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM images WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                status, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM images ORDER BY created_at DESC LIMIT $1", limit
            )

    return {
        "count": len(rows),
        "images": [
            {
                "image_id": str(r["id"]),
                "filename": r["filename"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@app.get("/api/stats", tags=["Analytics"])
async def get_stats():
    """Get processing statistics — total images, success rate, etc."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM images
        """)

    total = stats["total"]
    return {
        "total_images": total,
        "completed": stats["completed"],
        "pending": stats["pending"],
        "processing": stats["processing"],
        "failed": stats["failed"],
        "success_rate": f"{(stats['completed'] / total * 100):.1f}%" if total > 0 else "0%",
        "environment": ENVIRONMENT,
        "version": APP_VERSION,
    }
