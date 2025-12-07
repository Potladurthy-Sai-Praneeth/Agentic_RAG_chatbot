from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PineconeSearchInput(BaseModel):
    query: str = Field(description="The search query for the vector database.")

class GetChatMessagesResponseModel(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: datetime

class AssistantMessageResponseModel(BaseModel):
    message_id: str
    timestamp: datetime
    success: bool
    response: str

class UserMessageRequestModel(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: Optional[datetime] = None
    is_first_message: Optional[bool] = False

class GetAllUserSessionsResponseModel(BaseModel):
    session_id: str
    created_at: datetime
    title: Optional[str] = None

class CreateNewSessionResponseModel(BaseModel):
    session_id: str
    created_at: datetime

class DeleteSessionResponseModel(BaseModel):
    success: bool
    message: str

class HealthCheckResponseModel(BaseModel):
    status: str
    message: str