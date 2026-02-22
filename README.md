<img width="967" height="1115" alt="image" src="https://github.com/user-attachments/assets/90542f60-557e-49e6-a973-eb3ea2a7ffe3" /># HTX Take-Home Assessment — Image Processing Pipeline API

## Project Overview

This project implements a RESTful Image Processing Pipeline API using **FastAPI**.

The system supports uploading JPG/PNG images and automatically performs the following:

* Extracts basic image metadata (width, height, format, file size)
* Generates 2 thumbnails (small and medium)
* Generates an AI caption using an open-source BLIP model
* Stores processing results in a SQLite database
* Tracks processing status and processing statistics

Processing is **non-blocking**:

* Upload requests return immediately with a unique `image_id`
* Image processing is handled asynchronously in the background

---

## Tech Stack

* FastAPI (REST API Framework)
* Uvicorn (ASGI Server)
* SQLite (Data storage)
* Pillow (Image processing)
* HuggingFace Transformers (BLIP Captioning Model)
* PyTorch (Model inference)
* Pytest (Basic unit testing)

---

## Repository Structure

```
HTX-THA/
├── app/
│   ├── main.py
│   ├── processing.py
│   ├── db.py
│   └── schemas.py
├── tests/
│   └── test_api.py
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Installation & Setup Instructions

### 1. Clone the repository

```
git clone https://github.com/huixuqn/HTX-THA.git
cd HTX-THA
```

### 2. Create a virtual environment

```
python3 -m venv .venv
```

### 3. Activate the virtual environment

```
source .venv/bin/activate
```

### 4. Install dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run the API server

```
uvicorn app.main:app --reload
```

API Documentation (Swagger UI) is available at:

```
http://127.0.0.1:8000/docs
```

---

## Example Usage

### Upload Image

```
curl -F "file=@/path/to/your/image.jpg" http://127.0.0.1:8000/api/images
```

Example Response:

```
{
  "image_id": "uuid",
  "status": "processing"
}
```

---

### Get Image Processing Result

```
curl http://127.0.0.1:8000/api/images/<image_id>
```

Example Response:

```
{
  "status": "success",
  "data": {
    "image_id": "img123",
    "original_name": "photo.jpg",
    "processed_at": "2024-03-10T10:00:00Z",
    "metadata": {
      "width": 1920,
      "height": 1080,
      "format": "jpg",
      "size_bytes": 2048576,
      "caption": "red panda cubs"
    },
    "thumbnails": {
      "small": "http://127.0.0.1:8000/api/images/img123/thumbnails/small",
      "medium": "http://127.0.0.1:8000/api/images/img123/thumbnails/medium"
    }
  },
  "error": null
}
```

Additional information (e.g. caption) is included under `metadata`.

---

### List All Images

```
curl http://127.0.0.1:8000/api/images
```

Returns a list of processed or processing images in the required response format.

---

### Download Thumbnail

```
curl -o thumb.jpg http://127.0.0.1:8000/api/images/<image_id>/thumbnails/small
```

---

### Get Processing Statistics

```
curl http://127.0.0.1:8000/api/stats
```

Example Response:

```
{
  "total": 3,
  "failed": 1,
  "success_rate": "66.67%",
  "average_processing_time_seconds": 0.42
}
```

---

## Processing Pipeline Explanation

### Upload Phase

1. POST `/api/images` validates uploaded file type (only JPG and PNG allowed)
2. Image is saved locally
3. A record is inserted into SQLite with:

   * status = "processing"
   * created_at timestamp
   * file details (filename, mime type, file size)
4. Endpoint returns immediately with a unique `image_id`

### Background Processing (Non-Blocking)

A FastAPI background task performs:

1. Metadata extraction (width, height, format, file size)
2. Thumbnail generation (small + medium)
3. AI caption generation using BLIP model
4. Database update:

   * status = "success" or "failed"
   * processed_at timestamp
   * processing time
   * thumbnail paths
   * caption or error message

This design ensures uploads are not blocked while processing occurs.

---

## Error Handling & Logging

* Invalid file types return HTTP 400
* Processing failures:

  * Image record becomes `status = "failed"`
  * Error message stored in `error` field
* Processing logs are handled using Python logging.

---

## Testing (Basic Unit Tests)

Run:

```
pytest
```

Tests cover:

* Root endpoint availability
* Invalid upload handling
* `/api/stats` response format
* Basic endpoint functionality

---

## AI Captioning Notes

Captions are generated locally using an open-source BLIP model via HuggingFace Transformers.

Prompt conditioning and deterministic decoding were used to reduce hallucinated contextual details (e.g. incorrect locations), though minor inaccuracies may still occur due to model limitations.

