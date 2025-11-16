from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from contextlib import asynccontextmanager
from Chat.chat_service import ChatService
from Chat.chat_pydantic_models import *
from Chat.jwt_utils import *
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

chat_db: Optional[ChatService] = None


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global chat_db
    
    # Startup
    logger.info("Starting Chat Service API...")
    try:
        chat_db = ChatService()
        await chat_db.initialize()
        logger.info("Chat Service API started successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to start Chat Service API: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Chat Service API...")
        if chat_db:
            await chat_db.close()
        logger.info("Chat Service API shut down successfully")


# Initialize FastAPI app
app = FastAPI(
    title="Chat Service API",
    description="FastAPI service for Cassandra-based chat message persistence and session management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat/{session_id}/add-message", status_code=status.HTTP_201_CREATED,
          summary="Store a chat message",
          response_description="Message stored successfully",
          response_model= StoreChatMessageResponseModel,
          tags=["Chat Messages"]
          )
async def store_chat_message(session_id: str, chat_message:StoreChatMessageRequestModel, current_user: Dict = Depends(get_current_user)):
    """Store a chat message in the database."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        response = await chat_db.store_message(
            session_id=session_id,
            user_id=user_id,
            message_id=chat_message.message_id,
            role=chat_message.role,
            content=chat_message.content,
            timestamp=chat_message.timestamp
        )
        
        if response:
            logger.info(f"Chat message stored successfully: {response['message_id']}")
            return StoreChatMessageResponseModel(
               success=True,
               message_id=response['message_id'],
               timestamp=response['timestamp'],
               message = "Message stored successfully"
            )
    except HTTPException as http_exc:
        raise http_exc
    except ValueError as ve:
        logger.error(f"Invalid message_id format: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid message_id format: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"Error storing chat message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to store chat message: {str(e)}"
            )

@app.get('/chat/{session_id}/get-messages', response_model=List[GetAllChatMessageResponseModel],
          summary="Retrieve chat messages for a session",
          response_description="List of chat messages",
          tags=["Session Chat Messages"]
          )
async def get_chat_messages(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Retrieve all chat messages for a given session."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        messages = await chat_db.get_messages(
            session_id=session_id,
        )
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
        return [GetAllChatMessageResponseModel(**item) for item in messages]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving chat messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve chat messages: {str(e)}"
            )

@app.get('/chat/{session_id}/get-summary', response_model=GetSessionSummaryResponseModel,
          summary="Retrieve session summary",
          response_description="Session summary",
          tags=["Session Summary"]
          )
async def get_session_summary(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Retrieve the summary for a given session."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        summary = await chat_db.get_summary(
            session_id=session_id,
        )

        if summary:
            logger.info(f"Retrieved session summary for session {session_id}")
            return GetSessionSummaryResponseModel(**summary)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session summary not found"
            )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving session summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve session summary: {str(e)}"
            )

@app.post('/chat/{session_id}/insert-summary', status_code=status.HTTP_200_OK,
            summary="Insert session summary",
            response_description="Session summary inserted successfully",
            tags=["Session Summary"]
            )
async def insert_session_summary(session_id: str, summary: InsertSessionSummaryRequestModel, current_user: Dict = Depends(get_current_user)):
    """Insert or update the summary for a given session."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        response = await chat_db.insert_summary(
            session_id=session_id,
            user_id=user_id,
            summary=summary.summary,
            message_count=summary.message_count,
            timestamp=summary.timestamp
        )

        logger.info(f"Inserted session summary for session {session_id}")
        return InsertSessionSummaryResponseModel(
            success=True,
            message="Session summary inserted successfully"
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error inserting session summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to insert session summary: {str(e)}"
            )

@app.get('/chat/{session_id}/get-message-count',
         response_model=GetMessageCountResponseModel,
         summary="Retrieve message count for a session",
         response_description="Message count retrieved successfully",
         tags=["Session Message Count"]
         )
async def get_message_count(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Retrieve the message count for a given session."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        message_count = await chat_db.get_message_count(
            session_id=session_id,
        )

        logger.info(f"Retrieved message count for session {session_id}: {message_count}")
        return GetMessageCountResponseModel(
            session_id=session_id,
            message_count=message_count
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving message count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve message count: {str(e)}"
            )

@app.delete('/chat/{session_id}/delete', status_code=status.HTTP_200_OK,
            response_model=DeleteChatMessagesResponseModel,
            summary="Delete all chat messages for a session",
            response_description="Chat messages deleted successfully",
            tags=["Session Chat Messages"]
            )
async def delete_chat_messages(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete all chat messages for a given session."""
    if not chat_db:
        logger.error("Chat service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        await chat_db.delete_session(
            session_id=session_id,
        )

        logger.info(f"Deleted all chat messages for session {session_id}")
        return DeleteChatMessagesResponseModel(
            success=True,
            message="All chat messages deleted successfully"
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error deleting chat messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to delete chat messages: {str(e)}"
            )

@app.get('/health',
         status_code=status.HTTP_200_OK,
         summary="Health Check",
         description="Endpoint to check the health status of the User Management Service.",
         response_model = HealthCheckResponseModel)
async def health_check():
    try:
        if not chat_db:
            logger.error("Chat database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat database service is not available"
            )
        
        db_healthy = await chat_db.health_check()
        if not db_healthy:
            logger.error("Chat database health check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat database service is unhealthy"
            )

        logger.info("Health check passed")
        return HealthCheckResponseModel(
            status="healthy",
            message="Chat Service is healthy."
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get('/', status_code=status.HTTP_200_OK,
        summary="Welcome Endpoint",
        description="Welcome endpoint for the Chat Service API."
        )
async def root():
    """Welcome endpoint for the Chat Service API."""
    return {
        "service": "Chat Service API",
        "status": "running",
        "message": "Welcome to the Chat Service API!",
        "endpoints": {
            "POST /chat/{session_id}/add-message": "Store a chat message",
            "GET /chat/{session_id}/get-messages": "Retrieve chat messages for a session",
            "GET /chat/{session_id}/get-summary": "Retrieve session summary",
            "POST /chat/{session_id}/insert-summary": "Insert session summary",
            "GET /chat/{session_id}/get-message-count": "Retrieve message count for a session",
            "DELETE /chat/{session_id}/delete": "Delete all chat messages for a session",
            "GET /health": "Health Check Endpoint"
        }
    }

if __name__ == "__main__":
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )