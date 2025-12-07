from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class AddMessageResponseModel(BaseModel):
    message: str
    needs_summarization: bool
    success: bool

class AddMessageRequestModel(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class GetCachedMessagesResponseModel(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class GetMessageCountResponseModel(BaseModel):
    count: int

class TrimCacheResponseModel(BaseModel):
    message: str
    success: bool

class UpdateCacheSummaryResponseModel(BaseModel):
    message: str
    success: bool

class UpdateCacheSummaryRequestModel(BaseModel):
    summary: str
    timestamp: Optional[datetime] = None

class GetCacheSummaryResponseModel(BaseModel):
    summary: Optional[str]
    success: bool

class ClearCacheResponseModel(BaseModel):
    message: str
    success: bool

class CacheHealthResponseModel(BaseModel):
    status: str
    details: Optional[Dict[str, str]] = None

class SessionExistsResponseModel(BaseModel):
    exists: bool
    success: bool