from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class StoreChatMessageResponseModel(BaseModel):
    message_id: str
    timestamp: datetime
    success: bool
    message: Optional[str] = None

class StoreChatMessageRequestModel(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: Optional[datetime] = None

class GetAllChatMessageRequestModel(BaseModel):
    session_id: str

class GetAllChatMessageResponseModel(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: datetime

class GetSessionSummaryResponseModel(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    summary: Optional[str] = None
    last_updated: Optional[datetime] = None
    message_count: Optional[int] = None
    success: bool = True

class GetSessionSummaryRequestModel(BaseModel):
    session_id: str

class InsertSessionSummaryRequestModel(BaseModel):
    summary: str
    message_count: int
    timestamp: Optional[datetime] = None

class InsertSessionSummaryResponseModel(BaseModel):
    success: bool
    message: Optional[str] = None

class GetMessageCountResponseModel(BaseModel):
    session_id: str
    message_count: int
class GetMessageCountRequestModel(BaseModel):
    session_id: str


class DeleteChatMessagesRequestModel(BaseModel):
    session_id: str
class DeleteChatMessagesResponseModel(BaseModel):
    success: bool
    message: Optional[str] = None

class HealthCheckResponseModel(BaseModel):
    status: str
    message: str



