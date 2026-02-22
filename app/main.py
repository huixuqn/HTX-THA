import uuid
import logging
import datetime as dt
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse

from .db import init_db, get_conn
from .schemas import ImageCreateResponse, ImageEnvelope, ImageData, StatsResponse
from .processing import (
    ORIGINALS_DIR,
    ensure_dirs,
    extract_metadata,
    make_thumbnails,
    generate_caption_local,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("image-pipeline-api")

app = FastAPI(title="Image Pipeline API")


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    init_db()


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def process_image_job(image_id: str) -> None:
    """
    Background job: open image, compute metadata, thumbnails, caption, update DB.
    """
    start = time.perf_counter()

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
        if not row:
            return

        image_path = ORIGINALS_DIR / row["stored_filename"]

        try:
            size_bytes = int(row["size_bytes"] or image_path.stat().st_size)

            metadata = extract_metadata(image_path, size_bytes)
            small_path, medium_path = make_thumbnails(image_path, image_id)
            caption = generate_caption_local(image_path)

            processing_ms = int((time.perf_counter() - start) * 1000)
            processed_at = _now_iso()

            conn.execute(
                """
                UPDATE images
                SET status=?, width=?, height=?, format=?,
                    caption=?, processing_ms=?,
                    thumb_small_path=?, thumb_medium_path=?,
                    error=?, processed_at=?
                WHERE id=?
                """,
                (
                    "success",
                    metadata["width"],
                    metadata["height"],
                    metadata["format"],
                    caption,
                    processing_ms,
                    small_path,
                    medium_path,
                    None,
                    processed_at,
                    image_id,
                ),
            )
            conn.commit()
            logger.info("Processed image %s in %d ms", image_id, processing_ms)

        except Exception as e:
            processing_ms = int((time.perf_counter() - start) * 1000)
            processed_at = _now_iso()

            conn.execute(
                "UPDATE images SET status=?, error=?, processing_ms=?, processed_at=? WHERE id=?",
                ("failed", str(e), processing_ms, processed_at, image_id),
            )
            conn.commit()
            logger.exception("Failed processing image %s", image_id)


@app.get("/")
def root():
    return {"message": "API is working"}


@app.post("/api/images", response_model=ImageCreateResponse)
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPG and PNG are allowed.")

    image_id = str(uuid.uuid4())
    created_at = _now_iso()

    ext = ".jpg" if file.content_type == "image/jpeg" else ".png"
    stored_filename = f"{image_id}{ext}"
    image_path = ORIGINALS_DIR / stored_filename

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")

    image_path.write_bytes(contents)
    size_bytes = len(contents)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO images (
                id, original_filename, stored_filename, mime_type, size_bytes,
                created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                file.filename,
                stored_filename,
                file.content_type,
                size_bytes,
                created_at,
                "processing",
            ),
        )
        conn.commit()

    background_tasks.add_task(process_image_job, image_id)

    return ImageCreateResponse(image_id=image_id, status="processing")


@app.get("/api/images", response_model=List[ImageEnvelope])
def list_images(request: Request):
    base = str(request.base_url).rstrip("/")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC").fetchall()

    result: List[ImageEnvelope] = []
    for r in rows:
        image_id = r["id"]

        # Only include metadata/thumbnails when successful, like the example for failed cases
        metadata = {}
        thumbnails = {}

        if r["status"] == "success":
            thumbnails = {
                "small": f"{base}/api/images/{image_id}/thumbnails/small",
                "medium": f"{base}/api/images/{image_id}/thumbnails/medium",
            }
            
            fmt = (r["format"] or "").lower()
            if fmt == "jpeg":
                fmt = "jpg"
            metadata = {
                "width": r["width"],
                "height": r["height"],
                "format": fmt,
                "size_bytes": r["size_bytes"],
                "caption": r["caption"],  
            }

        data = ImageData(
            image_id=image_id,
            original_name=r["original_filename"],
            processed_at=r.get("processed_at") if hasattr(r, "get") else r["processed_at"],
            metadata=metadata,
            thumbnails=thumbnails,
        )
        result.append(ImageEnvelope(status=r["status"], data=data, error=r["error"]))

    return result


@app.get("/api/images/{image_id}", response_model=ImageEnvelope)
def get_image(image_id: str, request: Request):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Image not found.")

    base = str(request.base_url).rstrip("/")

    metadata = {}
    thumbnails = {}

    if r["status"] == "success":
        thumbnails = {
            "small": f"{base}/api/images/{image_id}/thumbnails/small",
            "medium": f"{base}/api/images/{image_id}/thumbnails/medium",
        }
        fmt = (r["format"] or "").lower()
        if fmt == "jpeg":
            fmt = "jpg"
        metadata = {
            "width": r["width"],
            "height": r["height"],
            "format": fmt,
            "size_bytes": r["size_bytes"],
            "caption": r["caption"],  # extra info allowed
        }

    data = ImageData(
        image_id=image_id,
        original_name=r["original_filename"],
        processed_at=r["processed_at"],
        metadata=metadata,
        thumbnails=thumbnails,
    )

    return ImageEnvelope(status=r["status"], data=data, error=r["error"])


@app.get("/api/images/{image_id}/thumbnails/{size}")
def get_thumbnail(image_id: str, size: str):
    if size not in ("small", "medium"):
        raise HTTPException(status_code=400, detail="size must be 'small' or 'medium'.")

    with get_conn() as conn:
        r = conn.execute(
            "SELECT thumb_small_path, thumb_medium_path, status FROM images WHERE id=?",
            (image_id,),
        ).fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Image not found.")

    if r["status"] != "success":
        raise HTTPException(status_code=409, detail="Thumbnails not ready (processing not successful).")

    path = r["thumb_small_path"] if size == "small" else r["thumb_medium_path"]
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found.")

    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/stats", response_model=StatsResponse)
def get_stats():
    with get_conn() as conn:
        total = int(conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"])
        failed = int(conn.execute("SELECT COUNT(*) AS c FROM images WHERE status='failed'").fetchone()["c"])
        success = int(conn.execute("SELECT COUNT(*) AS c FROM images WHERE status='success'").fetchone()["c"])

        avg_ms_row = conn.execute(
            "SELECT AVG(processing_ms) AS avg_ms FROM images WHERE processing_ms IS NOT NULL"
        ).fetchone()
        avg_ms = float(avg_ms_row["avg_ms"] or 0.0)

    success_rate = (success / total) * 100 if total else 0.0

    return StatsResponse(
        total=total,
        failed=failed,
        success_rate=f"{success_rate:.2f}%",
        average_processing_time_seconds=avg_ms / 1000.0,
    )