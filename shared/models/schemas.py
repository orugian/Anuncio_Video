from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum

class JobStatus(str, Enum):
    RECEIVED = "received"
    SCRAPING = "scraping"
    SEMANTIC_PROCESSING = "semantic_processing"
    PROMPT_GENERATION = "prompt_generation"
    AWAITING_APPROVAL = "awaiting_approval"
    VIDEO_GENERATION = "video_generation"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(BaseModel):
    id: Optional[UUID] = None
    user_id: str
    url: str
    status: JobStatus = JobStatus.RECEIVED
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ScrapedContent(BaseModel):
    job_id: UUID
    raw_json: Dict[str, Any]
    images: List[str]
    created_at: Optional[datetime] = None

class SemanticContext(BaseModel):
    job_id: UUID
    semantic_json: Dict[str, Any]
    created_at: Optional[datetime] = None

class VideoVersion(BaseModel):
    id: Optional[UUID] = None
    job_id: UUID
    version_number: int = 1
    prompt: str
    video_url: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None

class Feedback(BaseModel):
    id: Optional[UUID] = None
    version_id: UUID
    feedback_text: str
    parsed_feedback: Dict[str, Any]
    applied: bool = False
    created_at: Optional[datetime] = None
