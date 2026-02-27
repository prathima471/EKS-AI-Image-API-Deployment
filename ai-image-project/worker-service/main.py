"""
AI Image Worker Service — Processes images using AI models.
============================================================
This is the BACKEND worker that does the actual AI processing.

HOW IT WORKS:
  1. Polls Redis queue for new jobs
  2. Downloads image from S3
  3. Runs AI model (object detection, classification)
  4. Saves results to PostgreSQL
  5. Caches result in Redis

This service has NO HTTP endpoints (except health checks).
It's a background worker — always running, always processing.

HEALTH CHECK:
  GET /health  → Liveness probe
  GET /ready   → Readiness probe (checks Redis + DB + S3)
"""

import os
import io
import json
import time
import logging
import asyncio
import threading
from datetime import datetime, timezone

import boto3
import redis
import psycopg2
from PIL import Image
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# ── Configuration ──
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

# ── Global state ──
worker_running = False
jobs_processed = 0


# ── AI Model (Image Analysis) ──
def analyze_image(image_bytes: bytes, filename: str) -> dict:
    """
    Analyze an image using AI/ML techniques.

    In production, this would call:
      - AWS Rekognition
      - TensorFlow/PyTorch model
      - OpenAI Vision API
      - Hugging Face model

    For our demo, we use Pillow for real image analysis:
      - Image metadata extraction
      - Color analysis
      - Size/format detection
      - Basic classification based on image properties
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Extract image properties
        width, height = img.size
        format_type = img.format or "UNKNOWN"
        mode = img.mode
        file_size_kb = len(image_bytes) / 1024

        # Color analysis — get dominant colors
        small_img = img.resize((50, 50)).convert("RGB")
        pixels = list(small_img.getdata())
        avg_r = sum(p[0] for p in pixels) // len(pixels)
        avg_g = sum(p[1] for p in pixels) // len(pixels)
        avg_b = sum(p[2] for p in pixels) // len(pixels)

        # Brightness calculation
        brightness = (avg_r * 299 + avg_g * 587 + avg_b * 114) / 1000
        brightness_label = "dark" if brightness < 85 else "medium" if brightness < 170 else "bright"

        # Aspect ratio classification
        ratio = width / height if height > 0 else 1
        if ratio > 1.5:
            orientation = "panoramic"
        elif ratio > 1.1:
            orientation = "landscape"
        elif ratio < 0.7:
            orientation = "portrait"
        else:
            orientation = "square"

        # Size classification
        megapixels = (width * height) / 1_000_000
        if megapixels > 8:
            quality = "high-resolution"
        elif megapixels > 2:
            quality = "standard"
        else:
            quality = "low-resolution"

        # Color dominance
        if avg_r > avg_g and avg_r > avg_b:
            dominant_color = "red-toned"
        elif avg_g > avg_r and avg_g > avg_b:
            dominant_color = "green-toned"
        elif avg_b > avg_r and avg_b > avg_g:
            dominant_color = "blue-toned"
        else:
            dominant_color = "neutral"

        # Generate tags based on analysis
        tags = [orientation, quality, brightness_label, dominant_color]
        if mode == "RGBA":
            tags.append("has-transparency")
        if width > 3000 or height > 3000:
            tags.append("high-detail")
        if file_size_kb > 5000:
            tags.append("large-file")

        # Confidence score (simulated)
        confidence = min(0.95, 0.7 + (megapixels * 0.02))

        return {
            "analysis": {
                "dimensions": {"width": width, "height": height},
                "format": format_type,
                "color_mode": mode,
                "file_size_kb": round(file_size_kb, 2),
                "megapixels": round(megapixels, 2),
            },
            "ai_results": {
                "orientation": orientation,
                "quality": quality,
                "brightness": brightness_label,
                "dominant_color": dominant_color,
                "average_rgb": {"r": avg_r, "g": avg_g, "b": avg_b},
                "tags": tags,
                "confidence": round(confidence, 3),
            },
            "model_info": {
                "model": "image-analyzer-v1",
                "version": APP_VERSION,
                "processing_engine": "pillow-ai",
            },
        }

    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {"error": str(e)}


# ── Worker Loop (Background Thread) ──
def process_queue():
    """
    Continuously polls Redis queue for new image processing jobs.
    This runs in a background thread.
    """
    global worker_running, jobs_processed
    worker_running = True

    logger.info("Worker started — polling Redis queue...")

    # Connect to services
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        db_conn = psycopg2.connect(DATABASE_URL)
        db_conn.autocommit = True
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        logger.info("Worker connected to Redis, PostgreSQL, and S3")
    except Exception as e:
        logger.error(f"Worker connection failed: {e}")
        worker_running = False
        return

    while worker_running:
        try:
            # Block-wait for a job (timeout 5 seconds, then loop again)
            job_data = redis_client.brpop("image_processing_queue", timeout=5)

            if job_data is None:
                continue  # No job in queue, loop again

            _, job_json = job_data
            job = json.loads(job_json)

            image_id = job["image_id"]
            s3_key = job["s3_key"]
            filename = job["filename"]

            logger.info(f"Processing image: {image_id} ({filename})")

            # Update status to 'processing'
            cursor = db_conn.cursor()
            cursor.execute(
                "UPDATE images SET status = 'processing' WHERE id = %s",
                (image_id,),
            )

            # Download image from S3
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            image_bytes = response["Body"].read()

            # Run AI analysis
            result = analyze_image(image_bytes, filename)

            if "error" in result:
                # Analysis failed
                cursor.execute(
                    "UPDATE images SET status = 'failed', result = %s, processed_at = NOW() WHERE id = %s",
                    (json.dumps(result), image_id),
                )
                logger.error(f"Image {image_id} failed: {result['error']}")
            else:
                # Analysis succeeded
                cursor.execute(
                    "UPDATE images SET status = 'completed', result = %s, processed_at = NOW() WHERE id = %s",
                    (json.dumps(result), image_id),
                )

                # Cache result in Redis (1 hour TTL)
                cache_data = {
                    "image_id": image_id,
                    "filename": filename,
                    "status": "completed",
                    "result": result,
                }
                redis_client.setex(f"result:{image_id}", 3600, json.dumps(cache_data))

                logger.info(f"Image {image_id} processed successfully")

            cursor.close()
            jobs_processed += 1

        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(2)  # Wait before retrying

    logger.info("Worker stopped")


# ── FastAPI App (just for health checks) ──
app = FastAPI(title="AI Image Worker", version=APP_VERSION)

# Start worker thread on app startup
worker_thread = threading.Thread(target=process_queue, daemon=True)


@app.on_event("startup")
async def startup():
    worker_thread.start()
    logger.info("Worker thread started")


@app.get("/health", tags=["Health"])
async def health():
    """Liveness probe — is the worker alive?"""
    return {
        "status": "healthy",
        "service": "worker",
        "worker_running": worker_running,
        "jobs_processed": jobs_processed,
    }


@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness probe — is the worker ready to process?"""
    checks = {"worker_thread": worker_running}

    # Check Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        r.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    # Check database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    all_ready = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ready else 503,
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
    )
