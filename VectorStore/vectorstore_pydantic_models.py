from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class GeneratePresignedUrlRequestModel(BaseModel):
    """Request model for generating presigned URL"""
    file_name: str = Field(..., description="Name of the file to upload")
    expiration: Optional[int] = Field(3600, description="URL expiration time in seconds (default: 3600)")
    content_type: Optional[str] = Field(None, description="Content type/MIME type of the file")
    namespace: Optional[str] = Field(None, description="Optional namespace for Pinecone")


class GeneratePresignedUrlResponseModel(BaseModel):
    """Response model for presigned URL generation"""
    presigned_url: str = Field(..., description="Presigned URL for uploading file to S3")
    s3_key: str = Field(..., description="S3 object key where file will be stored")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    bucket: str = Field(..., description="S3 bucket name")
    file_name: str = Field(..., description="Original file name")
    success: bool = Field(True, description="Indicates if operation was successful")


class ProcessS3UploadRequestModel(BaseModel):
    """Request model for processing file from S3"""
    s3_key: str = Field(..., description="S3 object key of the uploaded file")
    namespace: Optional[str] = Field(None, description="Optional namespace for Pinecone")


class IngestDocumentsResponseModel(BaseModel):
    """Response model for document ingestion"""
    total_files: int = Field(..., description="Total number of files processed")
    total_documents: int = Field(..., description="Total number of documents loaded")
    total_chunks: int = Field(..., description="Total number of chunks created")
    success: bool = Field(..., description="Indicates if ingestion was successful")
    namespace: Optional[str] = Field(None, description="Namespace used for ingestion")
    message: Optional[str] = Field(None, description="Success or error message")


class SearchRequestModel(BaseModel):
    """Request model for searching Pinecone"""
    query: str = Field(..., description="Search query text")
    top_k: Optional[int] = Field(None, description="Number of results to return")
    namespace: Optional[str] = Field(None, description="Optional namespace to search in")
    filter: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filter")


class SearchResultModel(BaseModel):
    """Model for individual search result"""
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")


class SearchResponseModel(BaseModel):
    """Response model for search results"""
    results: List[SearchResultModel] = Field(..., description="List of search results")
    total_results: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original search query")


class DeleteNamespaceRequestModel(BaseModel):
    """Request model for deleting namespace"""
    namespace: str = Field(..., description="Namespace to delete")


class DeleteNamespaceResponseModel(BaseModel):
    """Response model for namespace deletion"""
    success: bool = Field(..., description="Indicates if deletion was successful")
    message: str = Field(..., description="Success message")
    namespace: str = Field(..., description="Deleted namespace")


class HealthCheckResponseModel(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Service status")
    message: str = Field(..., description="Status message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional status details")


class IndexStatsResponseModel(BaseModel):
    """Response model for index statistics"""
    total_vector_count: int = Field(..., description="Total number of vectors in the index")
    namespaces: Dict[str, Any] = Field(..., description="Namespace statistics")
    dimension: int = Field(..., description="Vector dimension")
    index_name: str = Field(..., description="Name of the Pinecone index")
    success: bool = Field(True, description="Indicates if operation was successful")


class IngestDocumentsRequestModel(BaseModel):
    """Request model for document ingestion"""
    source: str = Field(..., description="Source path (local file/directory) or S3 presigned URL")
    namespace: Optional[str] = Field(None, description="Optional namespace for Pinecone")
    cleanup_temp_files: Optional[bool] = Field(True, description="Whether to cleanup temporary files after processing")


class GeneratePresignedDownloadUrlRequestModel(BaseModel):
    """Request model for generating presigned download URL"""
    s3_key: str = Field(..., description="S3 object key")
    expiration: Optional[int] = Field(3600, description="URL expiration time in seconds (default: 3600)")


class GeneratePresignedDownloadUrlResponseModel(BaseModel):
    """Response model for presigned download URL generation"""
    presigned_url: str = Field(..., description="Presigned URL for downloading file from S3")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    success: bool = Field(True, description="Indicates if operation was successful")
