import uuid
from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from RAG.jwt_utils import get_current_user, verify_token
from RAG.context import current_jwt_token, current_jwt_token_string
from fastapi import Request, Response
from RAG.rag_service import RAGService
from RAG.rag_service_pydantic_models import *
from VectorStore.vectorstore_pydantic_models import HealthCheckResponseModel 

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

rag: Optional[RAGService] = None

# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global rag
    
    # Startup
    logger.info("Starting rag Service API...")
    try:
        rag = RAGService()
        await rag.initialize()
        logger.info("RAG Service API started successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to start RAG Service API: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down RAG Service API...")
        if rag:
            await rag.close()
        logger.info("RAG Service API shut down successfully")



# Initialize FastAPI app
app = FastAPI(
    title="RAG Service API",
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
    # Skip authentication for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)
    
    # Skip authentication for root and health endpoints
    if request.url.path in ["/", "/health"]:
        return await call_next(request)
    
    token_resetter = None
    token_string_resetter = None
    auth_header = request.headers.get("Authorization")
    
    try:
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
            try:
                user_data = verify_token(token)
                
                # SET THE CONTEXTVARS - both decoded payload and raw token string
                token_resetter = current_jwt_token.set(user_data)
                token_string_resetter = current_jwt_token_string.set(token)
            except HTTPException as http_exc:
                logger.warning(f"Token verification failed: {http_exc.detail}")
                # Return 401 response with CORS headers
                response = JSONResponse(
                    status_code=401,
                    content={"detail": http_exc.detail}
                )
                # Add CORS headers manually
                origin = request.headers.get("origin", "*")
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                return response
        else:
            # No valid Authorization header provided
            logger.warning("Missing or invalid Authorization header")
            response = JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"}
            )
            # Add CORS headers manually
            origin = request.headers.get("origin", "*")
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            return response
        
        response = await call_next(request)
        
    except Exception as e:
        # Return a 401 Unauthorized response for other exceptions
        logger.error(f"Authentication error: {str(e)}")
        response = JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"}
        )
        # Add CORS headers manually
        origin = request.headers.get("origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
        
    finally:
        # Always reset the contextvars after the request is done
        if token_resetter:
            current_jwt_token.reset(token_resetter)
        if token_string_resetter:
            current_jwt_token_string.reset(token_string_resetter)
            
    return response


@app.get("/rag/{session_id}/get-session-messages",response_model=List[GetChatMessagesResponseModel],
          summary="Retrieve chat messages for a session",
          response_description="List of chat messages",
          tags=["Session Chat Messages"]
          )
async def get_session_messages(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Retrieve all chat messages for a given session."""
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        messages = await rag.get_session_messages(session_id)
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
        return [GetChatMessagesResponseModel(**item) for item in messages]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving chat messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve chat messages: {str(e)}"
            )
  

@app.post("/rag/{session_id}/chat",
          response_model=AssistantMessageResponseModel,
          summary="Invoke the agent to respond to the user query",
          response_description="AI response from the agent",
          tags=["Assistant Message"]
          )
async def chat(session_id: str, user_message:UserMessageRequestModel, current_user: Dict = Depends(get_current_user)):
    """Invoke the agent to respond to the user query.
    
    Note: The message_id is generated by the backend as a TimeUUID (v1) to ensure 
    compatibility with Cassandra's TIMEUUID type. Any message_id provided in the 
    request will be ignored.
    """
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Generate TimeUUID (v1) for user message to match Cassandra TIMEUUID type
        user_message_id = str(uuid.uuid1())
        timestamp_now = datetime.utcnow()

        store_user_message = await rag.store_message(
            session_id=session_id,
            user_id=user_id,
            message_id=user_message_id,
            role=user_message.role,
            content=user_message.content,
            timestamp=timestamp_now
        )

        logger.info(f"Stored user message {user_message_id} for session {session_id}")


        assistant_response = await rag.chat(session_id, user_message.content)

        # Create a unique message ID for the assistant response (TimeUUID for Cassandra)
        assistant_message_id = str(uuid.uuid1())
        timestamp_assistant = datetime.utcnow()

        store_assistant_message = await rag.store_message(
            session_id=session_id,
            user_id=user_id,
            message_id=assistant_message_id,
            role="assistant",
            content=assistant_response,
            timestamp=timestamp_assistant
        )

        logger.info(f"Stored assistant message {assistant_message_id} for session {session_id}")

        if user_message.is_first_message:
            title_response = await rag.set_session_title(session_id, user_message.content)
            logger.info(f"Set session title for session {session_id}: {title_response.get('message','')}")


        logger.info(f"AI response for session {session_id}: {assistant_response}")
        return AssistantMessageResponseModel(
            message_id=assistant_message_id,
            timestamp=timestamp_assistant,
            success=True,
            response=assistant_response
        )
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error invoking agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to invoke agent: {str(e)}"
        )

@app.get("/rag/get-sessions", response_model=List[GetAllUserSessionsResponseModel],
        summary="Retrieve all session IDs for the current user",
        response_description="List of session IDs",
        tags=["User Sessions"]
        )
async def get_user_sessions(current_user: Dict = Depends(get_current_user)):
    """Retrieve all session IDs for the current user."""
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        sessions = await rag.get_sessions(user_id)
        logger.info(f"Retrieved {len(sessions)} sessions for user {user_id}")
        return [GetAllUserSessionsResponseModel(**item) for item in sessions]
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error retrieving user sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to retrieve user sessions: {str(e)}"
            )

@app.post("/rag/create-session", response_model=CreateNewSessionResponseModel,
        summary="Create a new session for the current user",
        response_description="Details of the newly created session",
        tags=["Create Session"]
        )
async def create_new_session(current_user: Dict = Depends(get_current_user)):
    """Create a new session for the current user."""
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        new_session = await rag.create_session(user_id)

        logger.info(f"Created new session {new_session['session_id']} for user {user_id}")
        return CreateNewSessionResponseModel(**new_session)
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error creating new session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to create new session: {str(e)}"
            )

@app.delete("/rag/{session_id}/delete-session", response_model=DeleteSessionResponseModel,
            summary="Delete the session and all associated messages",
            response_description="Result of the delete session operation",
            tags=["Delete Session"]
            )
async def delete_session(session_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete the session and all associated messages."""
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        delete_result = await rag.delete_session(user_id,session_id)

        logger.info(f"Deleted session {session_id} for user {user_id}")
        return DeleteSessionResponseModel(**delete_result)
    
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to delete session: {str(e)}"
            )

@app.get("/health", response_model=List[HealthCheckResponseModel],
        summary="Health check endpoint for RAG service",
        response_description="Health status of the RAG service",
        tags=["Health Check"]
        )
async def health_check():   
    """Health check endpoint for RAG service."""
    if not rag:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized"
        )
    try:
        health_check = await rag.verify_services()
        check = []
        for service in health_check:
            if health_check[service].get("status") == "healthy":
                logger.info(f"{service} Health: {health_check[service]['status']} - {health_check[service]['message']}")
                check.append(HealthCheckResponseModel(status=health_check[service]['status'], message=health_check[service]['message']))
            else:
                logger.error(f"{service} Health: {health_check[service]['status']} - {health_check[service]['message']}")
                check.append(HealthCheckResponseModel(status=health_check[service]['status'], message=health_check[service]['message']))
        return check
    
    except Exception as e:
        logger.error(f"Error during health check: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Health check failed: {str(e)}"
            )

@app.get('/', status_code=status.HTTP_200_OK,
        summary="Welcome Endpoint",
        description="Welcome endpoint for the Chat Service API."
        )
async def root():
    """Welcome endpoint for the Chat Service API."""
    return {
        "service": "RAG Service API",
        "status": "running",
        "message": "Welcome to the RAG Service API!",
        "endpoints": {
            "GET /rag/{session_id}/get-session-messages": "Retrieve chat messages for a session",
            "POST /rag/{session_id}/chat": "Invoke the agent to respond to the user query",
            "GET /rag/get-sessions": "Retrieve all session IDs for the current user",
            "POST /rag/create-session": "Create a new session for the current user",
            "DELETE /rag/{session_id}/delete-session": "Delete the session and all associated messages",
            "GET /health": "Health check endpoint for RAG service"
        }
    }
            

if __name__ == "__main__":
    
    uvicorn.run(
        "rag_api:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="info"
    )