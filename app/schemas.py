from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class VideoProcessingResult(BaseModel):
    video_id: str
    status: ProcessingStatus
    zip_path: Optional[str] = None
    frame_count: Optional[int] = None
    error: Optional[str] = None

class BatchProcessingResponse(BaseModel):
    batch_id: str
    user_id: str
    total_videos: int
    videos: List[VideoProcessingResult]