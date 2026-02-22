from pydantic import BaseModel
from typing import Optional, Dict, Any


class ImageCreateResponse(BaseModel):
    image_id: str
    status: str


class ImageData(BaseModel):
    image_id: str
    original_name: Optional[str] = None
    processed_at: Optional[str] = None
    metadata: Dict[str, Any]
    thumbnails: Dict[str, str]


class ImageEnvelope(BaseModel):
    status: str
    data: ImageData
    error: Optional[str] = None



class StatsResponse(BaseModel):
    total: int
    failed: int
    success_rate: str
    average_processing_time_seconds: float