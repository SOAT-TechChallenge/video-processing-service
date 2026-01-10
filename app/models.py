from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class VideoProcessingRequest(BaseModel):
    video_id: str
    user_id: str
    filename: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    zip_file_path: Optional[str] = None