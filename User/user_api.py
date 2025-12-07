from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict
import logging
from contextlib import asynccontextmanager
from User.user_service import UserService
from User.user_response_pydantic_models import *
from User.utils import *
from User.jwt_utils import *
from datetime import timedelta
import uvicorn
from fastapi import Request, Response
from User.context import current_jwt_token


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


user_db: Optional[UserService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global user_db

    try:
        user_db = UserService()
        await user_db.initialize()
        logger.info("Connected to the user database.")
        yield
    except Exception as e:
        logger.error(f"Error connecting to the user database: {e}")
        raise
    finally:
        if user_db:
            await user_db.close()
            logger.info("Shut down the user database.")


# Initialize FastAPI app
app = FastAPI(
    title="User Management Service",
    description="FastAPI service for managing user authentication and registration",
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


@app.post("/user/register", 
          response_model=RegisterResponseModel, 
          status_code=status.HTTP_201_CREATED,
          summary="Register a new user",
          description="Endpoint to register a new user with email and password.")
async def register_user(user: RegisterRequestModel):
    try:

        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        user_id = await user_db.register_user(user.email,user.username ,user.password)

        if not user_id:
            logger.warning("Failed to register user")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data or user already exists"
            )
        
        response = RegisterResponseModel(
            success=True,
            message="User registered successfully."
        )
        return response
    except HTTPException as http_exc:
        if http_exc.status_code == status.HTTP_400_BAD_REQUEST:
            return RegisterResponseModel(
                success=False,
                message="User registration failed: " + http_exc.detail
            )
        else:
            raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    

@app.post("/user/login", 
          response_model=LoginResponseModel, 
          status_code=status.HTTP_200_OK,
          summary="User login",
          description="Endpoint for user login with email and password.")
async def login_user(login_request: LoginRequestModel):
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        user_id = await user_db.login(login_request.user, login_request.password)

        if not user_id:
            logger.warning(f"Authentication failed for user:{login_request.user}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password. Combination does not match."
            )
        
         # Create JWT tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user_id)},  
            expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id)}  
        )
        
        response = LoginResponseModel(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return response
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.post('/user/add-session', 
          response_model= AddSessionResponseModel,
          status_code=status.HTTP_200_OK,
          summary="Add session to user Profile",
          description="Endpoint to add a new session to the user profile.")
async def add_session_to_user(session: AddSessionRequestModel, current_user: Dict = Depends(get_current_user)):
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        session_id = await user_db.add_session(session.session_id, user_id)
        if not session_id:
            logger.warning(f"Failed to add session for user_id:{user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add session to user profile."
            )

        logger.info(f"Session {session.session_id} added successfully for user_id:{user_id}")
        return AddSessionResponseModel(
            success=True,
            message="Session added successfully."
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get('/user/get-sessions',
         response_model=GetSessionsResponseModel,
         status_code=status.HTTP_200_OK,
         summary="Get user sessions",
         description="Endpoint to retrieve all sessions associated with the authenticated user.")
async def get_sessions(current_user: Dict = Depends(get_current_user)):
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        sessions = await user_db.get_sessions(user_id)
        logger.info(f"Retrieved {len(sessions)} sessions for user_id:{user_id}")
        return GetSessionsResponseModel(
            success=True,
            sessions=sessions
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.delete('/user/delete-session',
            status_code=status.HTTP_200_OK,
            response_model = DeleteSessionResponseModel,
            summary="Delete a user session",
            description="Endpoint to delete the authenticated user's session.")
async def delete_session(session: DeleteSessionRequestModel, current_user: Dict = Depends(get_current_user)):
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        session_id = session.session_id
        user_id = current_user.get("user_id")

        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        deleted = await user_db.delete_session(user_id, session_id)
        if not deleted:
            logger.warning(f"Failed to delete session for user_id:{user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete session from user profile."
            )

        logger.info(f"Session {session.session_id} deleted successfully for user_id:{user_id}")
        return DeleteSessionResponseModel(
            success=True,
            message="Session deleted successfully."
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.delete('/user/delete-user',
            status_code=status.HTTP_200_OK,
            response_model=DeleteUserResponseModel,
            summary="Delete user account",
            description="Endpoint to delete the authenticated user's account.")
async def delete_user(current_user: Dict = Depends(get_current_user)):
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        deleted = await user_db.delete_user(user_id)
        if not deleted:
            logger.warning(f"Failed to delete user account for user_id:{user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete user account."
            )

        logger.info(f"User account deleted successfully for user_id:{user_id}")
        return DeleteUserResponseModel(
            success=True,
            message="User account deleted successfully."
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    
@app.get('/health',
         status_code=status.HTTP_200_OK,
         summary="Health Check",
         description="Endpoint to check the health status of the User Management Service.",
         response_model = HealthCheckResponseModel)
async def health_check():
    try:
        if not user_db:
            logger.error("User database not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is not available"
            )
        
        db_healthy = await user_db.health_check()
        if not db_healthy:
            logger.error("User database health check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User database service is unhealthy"
            )

        logger.info("Health check passed")
        return HealthCheckResponseModel(
            status="healthy",
            message="User Management Service is healthy."
        )
    
    except HTTPException as http_exc:
       raise http_exc
    except Exception as e:
       raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/")
async def root():
    return {
        "service": "User Management Service",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "POST /user/register": "Register a new user",
            "POST /user/login": "Login a user",
            "POST /user/add-session": "Add a new session",
            "GET /user/get-sessions": "Retrieve all sessions for a user",
            "DELETE /user/delete-session": "Delete a session",
            "DELETE /user/delete-user": "Delete user account",
            "GET /health": "Health Check Endpoint"
        }

    }

if __name__ == "__main__":
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )