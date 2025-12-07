from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from pydantic.networks import EmailStr
from datetime import datetime



class RegisterRequestModel(BaseModel):
    email: EmailStr = Field(..., description="The user's email address")
    password: str = Field(..., min_length=8, description="The user's password")
    username: str = Field(..., description="The user's username")
class RegisterResponseModel(BaseModel):
   success: bool = Field(..., description="Indicates if the registration was successful")
   message: str = Field(..., description="Detailed message about the registration outcome")


class LoginRequestModel(BaseModel):
    user: str = Field(..., description="The user's email or username")
    password: str = Field(..., description="The user's password")
class LoginResponseModel(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Type of the token")
    expires_in: int = Field(..., description="Expiration time of the access token in seconds")


class AddSessionRequestModel(BaseModel):
    session_id: str = Field(..., description="The session ID to be added to the user profile")
    created_at: Optional[datetime] = Field(None, description="The creation time of the session")

class AddSessionResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the session addition was successful")
    message: str = Field(..., description="Detailed message about the session addition outcome")


class GetSessionsRequestModel(BaseModel):
    pass
class GetSessionsResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the retrieval was successful")
    sessions: List[Dict] = Field(..., description="List of session dictionaries containing session_id and created_at")


class DeleteSessionRequestModel(BaseModel):
    session_id: str = Field(..., description="The session ID to be deleted from the user profile")
class DeleteSessionResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the session deletion was successful")
    message: str = Field(..., description="Detailed message about the session deletion outcome")


class GetSessionTitleResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the retrieval was successful")
    title: Optional[str] = Field(None, description="The title of the session")

class SetSessionTitleRequestModel(BaseModel):
    title: str = Field(..., description="The title to set for the session")

class SetSessionTitleResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the title update was successful")
    message: str = Field(..., description="Detailed message about the title update outcome")

class DeleteUserRequestModel(BaseModel):
    pass
class DeleteUserResponseModel(BaseModel):
    success: bool = Field(..., description="Indicates if the user deletion was successful")
    message: str = Field(..., description="Detailed message about the user deletion outcome")


class HealthCheckResponseModel(BaseModel):
    status: str = Field(..., description="Health status of the service")
    message: str = Field(..., description="Detailed health check message")
