"""FastAPI service for Redis Cache Management."""

from Cache.cache_pydantic_models import *
from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from contextlib import asynccontextmanager
from Cache.cache_service import RedisService
import uvicorn
from Cache.context import current_jwt_token
from fastapi import Request, Response
from Cache.jwt_utils import verify_token, get_current_user


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global cache instance
cache: Optional[RedisService] = None


# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global cache
    
    # Startup
    logger.info("Starting Cache Service API...")
    try:
        cache = RedisService()
        logger.info("Cache Service API started successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to start Cache Service API: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Cache Service API...")
        if cache:
            cache.close()
        logger.info("Cache Service API shut down successfully")


# Initialize FastAPI app
app = FastAPI(
    title="Cache Service API",
    description="FastAPI service for Redis-based chat message caching with write-through strategy",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for consistency (even though primarily called internally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token_resetter = None
    auth_header = request.headers.get("Authorization")
    
    try:
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
            user_data = verify_token(token)
            
            # SET THE CONTEXTVAR
            token_resetter = current_jwt_token.set(user_data)
        
        response = await call_next(request)
        
    except HTTPException as http_exc:
        # Re-raise HTTPException to preserve error details
        raise http_exc
    except Exception as e:
        # Return a 401 Unauthorized response for other exceptions
        logger.error(f"Authentication error: {str(e)}")
        response = Response("Unauthorized", status_code=401)
        
    finally:
        # Always reset the contextvar after the request is done
        if token_resetter:
            current_jwt_token.reset(token_resetter)
            
    return response


@app.post("/cache/{session_id}/message", status_code=status.HTTP_201_CREATED,
          summary="Add a message to the cache",
          response_description="Message added successfully",
          response_model= AddMessageResponseModel)
async def add_message(session_id: str, message: AddMessageRequestModel, current_user: Dict = Depends(get_current_user)):
    """Add a message to the cache for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        needs_summarization = cache.add_message(session_id, message.model_dump())
        logger.info(f"Message added to cache for session {session_id} by user {user_id}")
        return AddMessageResponseModel(
            message="Message added successfully",
            needs_summarization=needs_summarization,
            success=True
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error adding message to cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to add message to cache: {str(e)}"
            )

@app.get("/cache/{session_id}/messages", status_code=status.HTTP_200_OK,
         summary="Retrieve messages from the cache",
         response_description="List of cached messages",
         response_model= List[GetCachedMessagesResponseModel])
async def get_messages(session_id: str, limit: Optional[int] = 0, current_user: Dict = Depends(get_current_user)):
    """Retrieve messages from the cache for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        messages = cache.get_messages(session_id, limit)
        logger.info(f"Retrieved messages from cache for session {session_id} by user {user_id}")
        return [GetCachedMessagesResponseModel(**msg) for msg in messages]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving messages from cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve messages from cache: {str(e)}"
            )

@app.get("/cache/{session_id}/message_count", status_code=status.HTTP_200_OK,
         summary="Get cached message count for a session",
         response_description="Count of cached messages",
         response_model= GetMessageCountResponseModel)
async def get_message_count(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Get the count of cached messages for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        message_count = cache.get_message_count(session_id)
        logger.info(f"Retrieved message count from cache for session {session_id} by user {user_id}")
        return GetMessageCountResponseModel(count=message_count)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving message count from cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve message count from cache: {str(e)}"
            )

@app.delete("/cache/{session_id}/trim", status_code=status.HTTP_200_OK,
            summary="Trim the cache for a session",
            response_description="Cache trimmed successfully",
            response_model=TrimCacheResponseModel)
async def trim_cache(session_id: str, keep_last: Optional[int] = Query(None, gt=0),
                     current_user: Dict = Depends(get_current_user)):
    """Trim the cache for a given session to keep only the last `keep_last` messages."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        suc = cache.trim_cache(session_id, keep_last)
        logger.info(f"Trimmed cache for session {session_id} by user {user_id}")
        return TrimCacheResponseModel(
            message="Cache trimmed successfully",
            success=suc
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error trimming cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to trim cache: {str(e)}"
            )

@app.post("/cache/{session_id}/update-summary", status_code=status.HTTP_200_OK,
            summary="Update session summary in the cache",
            response_description="Session summary updated successfully",
            response_model=UpdateCacheSummaryResponseModel)
async def update_summary(session_id: str, summary: UpdateCacheSummaryRequestModel,
                         current_user: Dict = Depends(get_current_user)):
    """Update the session summary in the cache for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        success = cache.update_summary(session_id, summary.summary)
        logger.info(f"Updated session summary in cache for session {session_id} by user {user_id}")
        return UpdateCacheSummaryResponseModel(
            message="Session summary updated successfully",
            success=success
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error updating session summary in cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to update session summary in cache: {str(e)}"
            )

@app.get("/cache/{session_id}/get-summary", status_code=status.HTTP_200_OK,
            summary="Get session summary from the cache",
            response_description="Session summary retrieved successfully",
            response_model=GetCacheSummaryResponseModel)
async def get_summary(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Get the session summary from the cache for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        summary = cache.get_summary(session_id)
        logger.info(f"Retrieved session summary from cache for session {session_id} by user {user_id}")
        return GetCacheSummaryResponseModel(
            summary=summary,
            success=True
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving session summary from cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve session summary from cache: {str(e)}"
            )

@app.delete("/cache/{session_id}/clear", status_code=status.HTTP_200_OK,
            summary="Clear the cache for a session",
            response_description="Cache cleared successfully",
            response_model=ClearCacheResponseModel)
async def clear_cache(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Clear the cache for a given session."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        success = cache.clear_session(session_id)
        logger.info(f"Cleared cache for session {session_id} by user {user_id}")
        return ClearCacheResponseModel(
            message="Cache cleared successfully",
            success=success
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to clear cache: {str(e)}"
            )

@app.get("/cache/{session_id}/session-exists", status_code=status.HTTP_200_OK,
         summary="Check if a session exists in the cache",
         response_description="Session existence status",
         response_model= SessionExistsResponseModel)
async def session_exists(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Check if a session exists in the cache."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        exists = cache.check_session_existence(session_id)
        logger.info(f"Checked existence of session {session_id} in cache by user {user_id}")
        return SessionExistsResponseModel(exists=exists, success=True)
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error checking session existence in cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to check session existence in cache: {str(e)}"
            )

@app.get("/health", status_code=status.HTTP_200_OK,
         summary="Health check for the Cache Service",
         response_description="Health check status",
         response_model=CacheHealthResponseModel)
async def health_check():
    """Health check endpoint for the Cache Service."""
    if not cache:
        logger.error("Cache service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized"
        )

    try:
        is_healthy = cache.health_check()
        if is_healthy:
            logger.info("Cache service health check passed")
            return CacheHealthResponseModel(
                status="healthy",
                details={"status": "Cache service is operational"}
            )
        else:
            logger.error("Cache service health check failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cache service is unhealthy"
            )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error during health check: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Health check failed: {str(e)}"
            )

@app.get('/', status_code=status.HTTP_200_OK,
         summary="Root endpoint for Cache Service",
         response_description="Welcome message")
async def root():
    """Root endpoint for the Cache Service."""
    return {
        "service": "Cache Service API",
        "status": "running",
        "message": "Welcome to the Cache Service API",
        "endpoints": {
           "POST /cache/{session_id}/message": "Add a message to the cache",
           "GET /cache/{session_id}/messages": "Retrieve messages from the cache",
           "GET /cache/{session_id}/message_count": "Get cached message count for a session",
           "DELETE /cache/{session_id}/trim": "Trim the cache for a session",
           "POST /cache/{session_id}/update-summary": "Update session summary in the cache",
           "GET /cache/{session_id}/get-summary": "Get session summary from the cache",
           "DELETE /cache/{session_id}/clear": "Clear the cache for a session",
           "GET /cache/{session_id}/session-exists": "Check if a session exists in the cache",
           "GET /health": "Health check for the Cache Service"  ,
        }
    }


if __name__ == "__main__":
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )