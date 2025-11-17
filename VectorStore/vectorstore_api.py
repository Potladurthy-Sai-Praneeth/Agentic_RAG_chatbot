import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from VectorStore.vectorstore_service import PineconeService
from VectorStore.vectorstore_pydantic_models import *
from VectorStore.jwt_utils import get_current_user
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instance
pinecone_service: Optional[PineconeService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    global pinecone_service
    
    try:
        # Initialize service on startup
        pinecone_service = PineconeService()
        pinecone_service.create_index()
        logger.info("VectorStore Service API started successfully")
        yield
    except Exception as e:
        logger.error(f"Error initializing VectorStore service: {e}")
        raise
    finally:
        # Cleanup on shutdown
        logger.info("VectorStore Service API shut down successfully")


# Initialize FastAPI app
app = FastAPI(
    title="VectorStore Service API",
    description="FastAPI service for Pinecone vector store operations with S3 and local file upload support",
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


# ============================================================================
# INDEX MANAGEMENT ENDPOINTS
# ============================================================================

@app.get(
    "/vectorstore/index/stats",
    status_code=status.HTTP_200_OK,
    summary="Get index statistics",
    response_description="Index statistics retrieved successfully",
    response_model=IndexStatsResponseModel,
    tags=["Index Management"]
)
async def get_index_stats(
    current_user: Dict = Depends(get_current_user)
):
    """Retrieve statistics of the Pinecone index."""
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        stats = pinecone_service.get_index_stats()
        
        return IndexStatsResponseModel(
            total_vector_count=stats['total_vector_count'],
            namespaces=stats['namespaces'],
            dimension=stats['dimension'],
            index_name=stats['index_name'],
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error retrieving index stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve index stats: {str(e)}"
        )


# ============================================================================
# UPLOAD ENDPOINTS (S3 and Local)
# ============================================================================

@app.post(
    "/vectorstore/presigned-url",
    status_code=status.HTTP_200_OK,
    summary="Generate presigned URL for S3 upload",
    response_description="Presigned URL generated successfully",
    response_model=GeneratePresignedUrlResponseModel,
    tags=["Upload URL S3"]
)
async def generate_presigned_url(
    request: GeneratePresignedUrlRequestModel,
    current_user: Dict = Depends(get_current_user)
):
    """Generate a presigned URL for uploading a file to S3."""
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        result = pinecone_service.generate_s3_upload_url(
            file_name=request.file_name,
            expiration=request.expiration,
            content_type=request.content_type,
            user_id=user_id
        )
        
        logger.info(f"Generated presigned URL for user {user_id}, file: {request.file_name}")
        
        return GeneratePresignedUrlResponseModel(
            presigned_url=result['presigned_url'],
            s3_key=result['s3_key'],
            expires_in=result['expires_in'],
            bucket=result['bucket'],
            file_name=result['file_name'],
            success=True
        )
        
    except ValueError as e:
        logger.error(f"Value error generating presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}"
        )

@app.post(
    "/vectorstore/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process file directly (Local Upload)",
    response_description="File uploaded and processed successfully",
    response_model=IngestDocumentsResponseModel,
    tags=["Upload a single Local"]
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload (supports single files and zip archives)"),
    namespace: Optional[str] = Form(None, description="Optional namespace for Pinecone"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Upload a file directly via API (multipart/form-data) and process it into the vector store.
    The file is processed locally and ingested directly into Pinecone.
    Supports both single files and zip archives.
    """
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Read file content
        file_content = await file.read()
        file_name = file.filename or "uploaded_file"
        
        logger.info(f"Processing file upload from user {user_id}: {file_name}")
        
        # Process file using ingest_from_file_content
        stats = pinecone_service.ingest_from_file_content(
            file_content=file_content,
            file_name=file_name,
            namespace=namespace
        )
        
        logger.info(
            f"Successfully processed file upload: {file_name}, "
            f"chunks: {stats['total_chunks']}, files: {stats['total_files']}"
        )
        
        return IngestDocumentsResponseModel(
            total_files=stats['total_files'],
            total_documents=stats['total_documents'],
            total_chunks=stats['total_chunks'],
            success=stats['success'],
            namespace=stats.get('namespace'),
            message=f"Successfully ingested {stats['total_chunks']} chunks from {stats['total_files']} file(s)"
        )
        
    except ValueError as e:
        logger.error(f"Value error processing file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file upload: {str(e)}"
        )


@app.post(
    "/vectorstore/process-s3-upload",
    status_code=status.HTTP_201_CREATED,
    summary="Process file from S3 after upload",
    response_description="File processed successfully",
    response_model=IngestDocumentsResponseModel,
    tags=["Upload - S3"]
)
async def process_s3_upload(
    request: ProcessS3UploadRequestModel,
    current_user: Dict = Depends(get_current_user)
):
    """
    Process a file from S3 after upload is complete.
    This endpoint uses the S3 key to generate a presigned download URL,
    downloads the file from that URL, and ingests it into Pinecone.
    This endpoint can be called when an S3 upload completion event is received.
    Supports both single files and zip archives.
    """
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

        logger.info(f"Processing S3 upload for user {user_id}, S3 key: {request.s3_key}")
        
        # Process file from S3 using ingest_from_s3_key
        stats = pinecone_service.ingest_from_s3_key(
            s3_key=request.s3_key,
            namespace=request.namespace
        )
        
        logger.info(
            f"Successfully processed S3 upload: {request.s3_key}, "
            f"chunks: {stats['total_chunks']}, files: {stats['total_files']}"
        )
        
        return IngestDocumentsResponseModel(
            total_files=stats['total_files'],
            total_documents=stats['total_documents'],
            total_chunks=stats['total_chunks'],
            success=stats['success'],
            namespace=stats.get('namespace'),
            message=f"Successfully ingested {stats['total_chunks']} chunks from {stats['total_files']} file(s)"
        )
        
    except ValueError as e:
        logger.error(f"Value error processing S3 upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing S3 upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process S3 upload: {str(e)}"
        )


@app.post(
    "/vectorstore/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest documents from local path or S3 presigned URL",
    response_description="Documents ingested successfully",
    response_model=IngestDocumentsResponseModel,
    tags=["Ingestion"]
)
async def ingest_documents(
    request: IngestDocumentsRequestModel,
    current_user: Dict = Depends(get_current_user)
):
    """
    Ingest documents from a local file/directory path or S3 presigned URL.
    Supports both single files and zip archives.
    The method automatically routes to the appropriate ingestion function:
    - Local file paths: "/path/to/file.pdf" -> processed and ingested directly
    - Local directories: "/path/to/documents/" -> all supported files processed and ingested
    - Local zip files: "/path/to/archive.zip" -> extracted, processed, and ingested
    - S3 presigned URLs: "https://s3.amazonaws.com/bucket/file.pdf?presigned=..." -> downloaded from URL, processed, and ingested
    """
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        logger.info(f"Ingesting documents for user {user_id}, source: {request.source}")
        
        # Ingest documents using the universal ingest_documents method
        stats = pinecone_service.ingest_documents(
            source=request.source,
            namespace=request.namespace,
            cleanup_temp_files=request.cleanup_temp_files
        )
        
        logger.info(
            f"Successfully ingested documents from {request.source}, "
            f"chunks: {stats['total_chunks']}, files: {stats['total_files']}"
        )
        
        return IngestDocumentsResponseModel(
            total_files=stats['total_files'],
            total_documents=stats['total_documents'],
            total_chunks=stats['total_chunks'],
            success=stats['success'],
            namespace=stats.get('namespace'),
            message=f"Successfully ingested {stats['total_chunks']} chunks from {stats['total_files']} file(s)"
        )
        
    except ValueError as e:
        logger.error(f"Value error ingesting documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest documents: {str(e)}"
        )


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@app.post(
    "/vectorstore/search",
    status_code=status.HTTP_200_OK,
    summary="Search vector store",
    response_description="Search completed successfully",
    response_model=SearchResponseModel,
    tags=["Search"]
)
async def search_vector_store(
    request: SearchRequestModel,
    current_user: Dict = Depends(get_current_user)
):
    """Search for similar documents in the vector store."""
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        results = pinecone_service.search(
            query=request.query,
            top_k=request.top_k,
            namespace=request.namespace,
            filter=request.filter
        )
        
        # Convert Document objects to SearchResultModel
        results_list = [
            SearchResultModel(
                content=doc.page_content,
                metadata=doc.metadata
            )
            for doc in results
        ]
        
        return SearchResponseModel(
            results=results_list,
            total_results=len(results_list),
            query=request.query
        )
        
    except Exception as e:
        logger.error(f"Error searching vector store: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search vector store: {str(e)}"
        )


# ============================================================================
# NAMESPACE MANAGEMENT ENDPOINTS
# ============================================================================

@app.delete(
    "/vectorstore/namespace/{namespace}",
    status_code=status.HTTP_200_OK,
    summary="Delete namespace",
    response_description="Namespace deleted successfully",
    response_model=DeleteNamespaceResponseModel,
    tags=["Namespace Management"]
)
async def delete_namespace(
    namespace: str,
    current_user: Dict = Depends(get_current_user)
):
    """Delete all vectors in a namespace."""
    if not pinecone_service:
        logger.error("VectorStore service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VectorStore service not initialized"
        )
    
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            logger.error("User ID not found in token payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        success = pinecone_service.delete_namespace(namespace)
        
        return DeleteNamespaceResponseModel(
            success=success,
            message=f"Namespace '{namespace}' deleted successfully",
            namespace=namespace
        )
        
    except Exception as e:
        logger.error(f"Error deleting namespace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete namespace: {str(e)}"
        )


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    response_description="Service health status",
    response_model=HealthCheckResponseModel,
    tags=["Health"]
)
async def health_check():
    """Check the health status of the VectorStore service."""
    try:
        if not pinecone_service:
            return HealthCheckResponseModel(
                status="unhealthy",
                message="Service not initialized",
                details={"initialized": False}
            )
        
        # Check Pinecone connection
        index_info = pinecone_service.client.describe_index(pinecone_service.pinecone_index_name)
        
        return HealthCheckResponseModel(
            status="healthy",
            message="Service is operational",
            details={
                "initialized": True,
                "index_name": pinecone_service.pinecone_index_name,
                "index_status": index_info.status.get('state', 'unknown') if hasattr(index_info, 'status') else 'unknown'
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponseModel(
            status="unhealthy",
            message=f"Service error: {str(e)}",
            details={"error": str(e)}
        )


@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """Root endpoint"""
    return {
        "service": "VectorStore Service API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "index_management": [
                "GET /vectorstore/index/stats"
            ],
            "upload_s3": [
                "POST /vectorstore/presigned-url",
                "POST /vectorstore/process-s3-upload"
            ],
            "upload_local": [
                "POST /vectorstore/upload"
            ],
            "ingestion": [
                "POST /vectorstore/ingest"
            ],
            "search": [
                "POST /vectorstore/search"
            ],
            "namespace_management": [
                "DELETE /vectorstore/namespace/{namespace}"
            ],
            "health": [
                "GET /health"
            ]
        }
    }

if __name__ == "__main__":
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )