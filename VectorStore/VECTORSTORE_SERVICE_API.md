# VectorStore Service API Documentation

## Overview

The VectorStore Service API is a FastAPI-based microservice for managing personalized vector stores using Pinecone. It provides users with the ability to create, manage, and search their own vector stores by uploading files (including zip archives) or providing S3 presigned URLs. Documents are processed, chunked, and ingested into Pinecone for semantic search capabilities.

**Base URL**: `http://localhost:8004` (or configured port)  
**Version**: 1.0.0

---

## Authentication

Most endpoints require JWT Bearer token authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

The token should be obtained from the User Service `/login` endpoint. The token payload must contain:
- `user_id`: User identifier
- `type`: "access"

---

## Endpoints

### 1. Get Index Statistics

**Endpoint**: `GET /vectorstore/index/stats`

**Description**: Retrieve statistics about the Pinecone index, including total vector count, namespaces, and dimension.

**Authentication**: Required (Bearer Token)

**Response**: `200 OK`

**Response Model**: `IndexStatsResponseModel`
```json
{
  "total_vector_count": 1000,
  "namespaces": {
    "namespace1": {
      "vector_count": 500
    },
    "namespace2": {
      "vector_count": 500
    }
  },
  "dimension": 768,
  "index_name": "learning-chatbot-index",
  "success": true
}
```

**Response Fields**:
- `total_vector_count` (integer): Total number of vectors in the index
- `namespaces` (object): Dictionary of namespace statistics
- `dimension` (integer): Vector dimension (embedding size)
- `index_name` (string): Name of the Pinecone index
- `success` (boolean): Indicates if operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to retrieve index stats

---

### 2. Generate Presigned Upload URL (S3)

**Endpoint**: `POST /vectorstore/presigned-url`

**Description**: Generate a presigned URL for uploading a file to S3. After uploading to S3, use the `/vectorstore/process-s3-upload` endpoint to ingest the file.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "file_name": "document.pdf",
  "expiration": 3600,
  "content_type": "application/pdf"
}
```

**Request Model**: `GeneratePresignedUrlRequestModel`
- `file_name` (string, required): Name of the file to upload
- `expiration` (integer, optional): URL expiration time in seconds (default: 3600)
- `content_type` (string, optional): MIME type of the file

**Response**: `200 OK`

**Response Model**: `GeneratePresignedUrlResponseModel`
```json
{
  "presigned_url": "https://s3.amazonaws.com/bucket/uploads/user123/20240101/uuid.pdf?presigned=...",
  "s3_key": "uploads/user123/20240101/uuid.pdf",
  "expires_in": 3600,
  "bucket": "learning-chatbot-bucket",
  "file_name": "document.pdf",
  "success": true
}
```

**Response Fields**:
- `presigned_url` (string): Presigned URL for uploading file to S3
- `s3_key` (string): S3 object key where file will be stored
- `expires_in` (integer): URL expiration time in seconds
- `bucket` (string): S3 bucket name
- `file_name` (string): Original file name
- `success` (boolean): Indicates if operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: S3 is not configured or invalid request
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to generate presigned URL

**Notes**:
- The S3 key is organized by user ID and date for better organization
- After uploading to the presigned URL, call `/vectorstore/process-s3-upload` with the `s3_key` to ingest the file

---

### 3. Generate Presigned Download URL (S3)

**Endpoint**: `POST /vectorstore/presigned-download-url`

**Description**: Generate a presigned URL for downloading a file from S3.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "s3_key": "uploads/user123/20240101/uuid.pdf",
  "expiration": 3600
}
```

**Request Model**: `GeneratePresignedDownloadUrlRequestModel`
- `s3_key` (string, required): S3 object key
- `expiration` (integer, optional): URL expiration time in seconds (default: 3600)

**Response**: `200 OK`

**Response Model**: `GeneratePresignedDownloadUrlResponseModel`
```json
{
  "presigned_url": "https://s3.amazonaws.com/bucket/uploads/user123/20240101/uuid.pdf?presigned=...",
  "expires_in": 3600,
  "success": true
}
```

**Response Fields**:
- `presigned_url` (string): Presigned URL for downloading file from S3
- `expires_in` (integer): URL expiration time in seconds
- `success` (boolean): Indicates if operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: S3 is not configured or invalid request
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to generate presigned download URL

---

### 4. Process S3 Upload

**Endpoint**: `POST /vectorstore/process-s3-upload`

**Description**: Process a file from S3 after upload is complete. This endpoint downloads the file from S3, processes it (handles zip archives), and ingests it into Pinecone.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "s3_key": "uploads/user123/20240101/uuid.pdf",
  "namespace": "my-documents"
}
```

**Request Model**: `ProcessS3UploadRequestModel`
- `s3_key` (string, required): S3 object key of the uploaded file
- `namespace` (string, optional): Optional namespace for Pinecone (for user isolation)

**Response**: `201 Created`

**Response Model**: `IngestDocumentsResponseModel`
```json
{
  "total_files": 1,
  "total_documents": 5,
  "total_chunks": 15,
  "success": true,
  "namespace": "my-documents",
  "message": "Successfully ingested 15 chunks from 1 file(s)"
}
```

**Response Fields**:
- `total_files` (integer): Total number of files processed
- `total_documents` (integer): Total number of documents loaded
- `total_chunks` (integer): Total number of chunks created and ingested
- `success` (boolean): Indicates if ingestion was successful
- `namespace` (string, optional): Namespace used for ingestion
- `message` (string, optional): Success or error message

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Invalid S3 key or S3 not configured
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to process S3 upload

**Notes**:
- Supports both single files and zip archives
- If the file is a zip archive, it will be extracted and all supported files will be processed
- Documents are chunked according to configuration (default: 1500 characters with 300 overlap)

---

### 5. Upload File Directly (Local Upload)

**Endpoint**: `POST /vectorstore/upload`

**Description**: Upload a file directly via API (multipart/form-data) and process it into the vector store. The file is processed locally and ingested directly into Pinecone. Supports both single files and zip archives.

**Authentication**: Required (Bearer Token)

**Request**: `multipart/form-data`

**Form Fields**:
- `file` (file, required): File to upload (supports single files and zip archives)
- `namespace` (string, optional): Optional namespace for Pinecone

**Response**: `201 Created`

**Response Model**: `IngestDocumentsResponseModel`
```json
{
  "total_files": 1,
  "total_documents": 3,
  "total_chunks": 9,
  "success": true,
  "namespace": "my-documents",
  "message": "Successfully ingested 9 chunks from 1 file(s)"
}
```

**Supported File Types**:
- PDF (`.pdf`)
- Markdown (`.md`)
- Word Documents (`.docx`, `.doc`)
- Text Files (`.txt`)
- CSV (`.csv`)
- HTML (`.html`, `.htm`)

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Unsupported file type or invalid file
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to process file upload

**Notes**:
- Maximum file size depends on server configuration
- Zip archives are automatically extracted and all supported files are processed
- Files are temporarily stored during processing and cleaned up afterward

---

### 6. Ingest Documents

**Endpoint**: `POST /vectorstore/ingest`

**Description**: Ingest documents from a local file/directory path or S3 presigned URL. Supports both single files and zip archives. The method automatically routes to the appropriate ingestion function based on the source type.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "source": "/path/to/file.pdf",
  "namespace": "my-documents",
  "cleanup_temp_files": true
}
```

**Request Model**: `IngestDocumentsRequestModel`
- `source` (string, required): Source path or URL:
  - Local file: `/path/to/file.pdf`
  - Local directory: `/path/to/documents/`
  - Local zip file: `/path/to/archive.zip`
  - S3 presigned URL: `https://s3.amazonaws.com/bucket/file.pdf?presigned=...`
- `namespace` (string, optional): Optional namespace for Pinecone
- `cleanup_temp_files` (boolean, optional): Whether to cleanup temporary files after processing (default: true)

**Response**: `201 Created`

**Response Model**: `IngestDocumentsResponseModel`
```json
{
  "total_files": 2,
  "total_documents": 8,
  "total_chunks": 24,
  "success": true,
  "namespace": "my-documents",
  "message": "Successfully ingested 24 chunks from 2 file(s)"
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Invalid source format or unsupported file type
- `404 Not Found`: File or path not found
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to ingest documents

**Notes**:
- For local paths, ensure the service has read access to the file/directory
- For directories, all supported files are processed recursively
- Zip files are extracted and all supported files are processed
- S3 presigned URLs are downloaded and processed

---

### 7. Search Vector Store

**Endpoint**: `POST /vectorstore/search`

**Description**: Search for similar documents in the vector store using semantic similarity search.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "query": "What is machine learning?",
  "top_k": 10,
  "namespace": "my-documents",
  "filter": {
    "source_file": "document.pdf"
  }
}
```

**Request Model**: `SearchRequestModel`
- `query` (string, required): Search query text
- `top_k` (integer, optional): Number of results to return (default: 5 from config)
- `namespace` (string, optional): Optional namespace to search in
- `filter` (object, optional): Optional metadata filter (e.g., `{"source_file": "document.pdf"}`)

**Response**: `200 OK`

**Response Model**: `SearchResponseModel`
```json
{
  "results": [
    {
      "content": "Machine learning is a subset of artificial intelligence...",
      "metadata": {
        "source_file": "document.pdf",
        "file_path": "/path/to/document.pdf"
      }
    },
    {
      "content": "Deep learning uses neural networks...",
      "metadata": {
        "source_file": "document2.pdf",
        "file_path": "/path/to/document2.pdf"
      }
    }
  ],
  "total_results": 2,
  "query": "What is machine learning?"
}
```

**Response Fields**:
- `results` (array): List of search results
  - `content` (string): Document content (chunk)
  - `metadata` (object): Document metadata (source file, path, etc.)
- `total_results` (integer): Total number of results returned
- `query` (string): Original search query

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to search vector store

**Notes**:
- Results are ranked by similarity score (cosine similarity)
- Metadata filters allow searching within specific files or namespaces
- Use namespaces to isolate user-specific documents

---

### 8. Delete Namespace

**Endpoint**: `DELETE /vectorstore/namespace/{namespace}`

**Description**: Delete all vectors in a namespace. This permanently removes all documents ingested into the specified namespace.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `namespace` (string, required): Namespace to delete

**Response**: `200 OK`

**Response Model**: `DeleteNamespaceResponseModel`
```json
{
  "success": true,
  "message": "Namespace 'my-documents' deleted successfully",
  "namespace": "my-documents"
}
```

**Response Fields**:
- `success` (boolean): Indicates if deletion was successful
- `message` (string): Success message
- `namespace` (string): Deleted namespace

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: VectorStore service not initialized
- `500 Internal Server Error`: Failed to delete namespace

**Notes**:
- This operation is irreversible
- All vectors in the namespace will be permanently deleted
- Consider backing up important data before deletion

---

### 9. Health Check

**Endpoint**: `GET /health`

**Description**: Check the health status of the VectorStore service and Pinecone connection.

**Authentication**: Not required

**Response**: `200 OK`

**Response Model**: `HealthCheckResponseModel`
```json
{
  "status": "healthy",
  "message": "Service is operational",
  "details": {
    "initialized": true,
    "index_name": "learning-chatbot-index",
    "index_status": "Ready"
  }
}
```

**Response Fields**:
- `status` (string): Health status ("healthy" or "unhealthy")
- `message` (string): Status message
- `details` (object, optional): Additional health check details
  - `initialized` (boolean): Whether service is initialized
  - `index_name` (string): Pinecone index name
  - `index_status` (string): Index status

**Error Responses**:
- `200 OK`: Always returns 200, but status may be "unhealthy"

**Notes**:
- Performs a Pinecone index status check
- Returns "unhealthy" if service is not initialized or Pinecone connection fails

---

### 10. Root Endpoint

**Endpoint**: `GET /`

**Description**: Welcome endpoint that provides service information and available endpoints.

**Authentication**: Not required

**Response**: `200 OK`

**Response**:
```json
{
  "service": "VectorStore Service API",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "index_management": [
      "GET /vectorstore/index/stats"
    ],
    "upload_s3": [
      "POST /vectorstore/presigned-url",
      "POST /vectorstore/presigned-download-url",
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
```

---

## Data Types

### Common Types

- **string**: Text data
- **integer**: Numeric integer value
- **boolean**: true or false
- **object**: JSON object/dictionary

### Supported File Extensions

- `.pdf`: PDF documents
- `.md`: Markdown files
- `.docx`, `.doc`: Microsoft Word documents
- `.txt`: Plain text files
- `.csv`: CSV files
- `.html`, `.htm`: HTML files

---

## Configuration

The VectorStore Service uses a `config.yaml` file for configuration:

```yaml
pinecone:
  cloud: "aws"
  region: "us-east-1"
  top_k: 5
  min_nodes: 1
  max_nodes: 3

models:
  embedding:
    provider: "gemini"  # Options: "gemini", "openai"
    name: "models/embedding-001"
    dimension: 768

chunking:
  chunk_size: 1500
  chunk_overlap: 300
```

### Configuration Parameters

- **pinecone.cloud**: Cloud provider for Pinecone (e.g., "aws")
- **pinecone.region**: AWS region for Pinecone
- **pinecone.top_k**: Default number of search results
- **pinecone.min_nodes**: Minimum nodes for serverless index
- **pinecone.max_nodes**: Maximum nodes for serverless index
- **models.embedding.provider**: Embedding model provider ("gemini" or "openai")
- **models.embedding.name**: Embedding model name
- **models.embedding.dimension**: Vector dimension (embedding size)
- **chunking.chunk_size**: Maximum characters per chunk
- **chunking.chunk_overlap**: Overlap between chunks in characters

### Environment Variables

- `PINECONE_API_KEY`: Pinecone API key (required)
- `PINECONE_INDEX_NAME`: Pinecone index name (required)
- `GEMINI_API_KEY`: Google Gemini API key (required if using Gemini embeddings)
- `OPENAI_API_KEY`: OpenAI API key (required if using OpenAI embeddings)
- `S3_BUCKET_NAME`: S3 bucket name (optional, for S3 features)
- `AWS_ACCESS_KEY_ID`: AWS access key ID (optional, for S3 features)
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key (optional, for S3 features)
- `AWS_REGION`: AWS region (optional, default: "us-east-1")

---

## Integration Notes

### For Other Services

1. **Authentication**: Obtain a JWT access token from the User Service `/login` endpoint before calling VectorStore Service endpoints.

2. **User Isolation**: 
   - Use namespaces to isolate documents by user (e.g., `namespace: user_{user_id}`)
   - S3 upload URLs are automatically organized by user ID

3. **File Upload Flow**:
   - **S3 Flow**: 
     1. Call `/vectorstore/presigned-url` to get upload URL
     2. Upload file to presigned URL using PUT request
     3. Call `/vectorstore/process-s3-upload` with `s3_key` to ingest
   - **Direct Upload Flow**:
     1. Call `/vectorstore/upload` with file in multipart/form-data
     2. File is automatically processed and ingested

4. **Document Ingestion**:
   - Documents are automatically chunked according to configuration
   - Chunks are embedded and stored in Pinecone
   - Metadata includes source file information

5. **Search**:
   - Use semantic similarity search for finding relevant documents
   - Filter by namespace to search within user-specific documents
   - Use metadata filters to search within specific files

6. **Error Handling**: Always check for:
   - `401 Unauthorized`: Re-authenticate and retry
   - `503 Service Unavailable`: Service may be starting up or Pinecone connection lost
   - `500 Internal Server Error`: Log error and retry with exponential backoff

7. **Namespace Management**:
   - Use namespaces to organize documents by user, project, or category
   - Delete namespaces when cleaning up user data
   - Namespace deletion is irreversible

---

## Example Usage

### Upload File Directly

```bash
curl -X POST "http://localhost:8004/vectorstore/upload" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@document.pdf" \
  -F "namespace=my-documents"
```

**Response**:
```json
{
  "total_files": 1,
  "total_documents": 5,
  "total_chunks": 15,
  "success": true,
  "namespace": "my-documents",
  "message": "Successfully ingested 15 chunks from 1 file(s)"
}
```

### Upload via S3

```bash
# Step 1: Get presigned URL
curl -X POST "http://localhost:8004/vectorstore/presigned-url" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "document.pdf",
    "expiration": 3600
  }'

# Step 2: Upload to S3 (using presigned URL from step 1)
curl -X PUT "<presigned_url>" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf

# Step 3: Process S3 upload
curl -X POST "http://localhost:8004/vectorstore/process-s3-upload" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "s3_key": "uploads/user123/20240101/uuid.pdf",
    "namespace": "my-documents"
  }'
```

### Ingest from Local Path

```bash
curl -X POST "http://localhost:8004/vectorstore/ingest" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "/path/to/documents/",
    "namespace": "my-documents"
  }'
```

### Search Vector Store

```bash
curl -X POST "http://localhost:8004/vectorstore/search" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "top_k": 5,
    "namespace": "my-documents"
  }'
```

**Response**:
```json
{
  "results": [
    {
      "content": "Machine learning is a subset of artificial intelligence...",
      "metadata": {
        "source_file": "document.pdf",
        "file_path": "/path/to/document.pdf"
      }
    }
  ],
  "total_results": 1,
  "query": "What is machine learning?"
}
```

### Delete Namespace

```bash
curl -X DELETE "http://localhost:8004/vectorstore/namespace/my-documents" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "success": true,
  "message": "Namespace 'my-documents' deleted successfully",
  "namespace": "my-documents"
}
```

### Get Index Statistics

```bash
curl -X GET "http://localhost:8004/vectorstore/index/stats" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "total_vector_count": 1000,
  "namespaces": {
    "my-documents": {
      "vector_count": 500
    }
  },
  "dimension": 768,
  "index_name": "learning-chatbot-index",
  "success": true
}
```

---

## Typical Workflow

### Document Ingestion Workflow

1. **Upload File**: 
   - Option A: Use `/vectorstore/upload` for direct upload
   - Option B: Use `/vectorstore/presigned-url` → upload to S3 → `/vectorstore/process-s3-upload`
   - Option C: Use `/vectorstore/ingest` with local path or S3 URL

2. **Processing**: 
   - File is loaded using appropriate document loader
   - Documents are split into chunks (configurable size and overlap)
   - Chunks are embedded using configured embedding model
   - Vectors are stored in Pinecone with metadata

3. **Search**: 
   - Use `/vectorstore/search` with query text
   - Optionally filter by namespace or metadata
   - Results are ranked by similarity

4. **Management**: 
   - Use namespaces to organize documents by user/project
   - Delete namespaces when cleaning up data

### User-Specific Vector Store

To create a personalized vector store for each user:

1. Use user-specific namespace: `namespace: user_{user_id}`
2. All uploads for that user use the same namespace
3. Search within user namespace: `namespace: user_{user_id}`
4. Delete user namespace when user account is deleted

---

## Performance Considerations

1. **Chunking**: Configure `chunk_size` and `chunk_overlap` based on your document types and use cases
2. **Embedding Model**: Choose embedding model based on language support and quality requirements
3. **Batch Processing**: For large files, consider processing in batches
4. **Namespace Organization**: Use namespaces to improve search performance and organization
5. **Index Configuration**: Configure Pinecone index size based on expected vector count

---

## Security Considerations

1. **Authentication**: All endpoints (except `/health` and `/`) require valid JWT tokens
2. **User Isolation**: Use namespaces to isolate documents by user
3. **S3 Security**: Ensure S3 bucket has proper access controls and presigned URLs have appropriate expiration
4. **Token Validation**: User ID is extracted from JWT token - ensure tokens are properly validated
5. **File Validation**: Validate file types and sizes before processing
6. **Path Traversal**: Validate file paths to prevent directory traversal attacks

---

## Error Scenarios

### Pinecone Connection Lost

If Pinecone connection is lost:
- Health check will return `unhealthy` status
- All operations will fail with `500 Internal Server Error`
- Service will attempt to reconnect automatically

### S3 Not Configured

If S3 is not configured:
- S3-related endpoints will return `400 Bad Request`
- Direct upload endpoint (`/vectorstore/upload`) will still work
- Local path ingestion will still work

### Unsupported File Type

If file type is not supported:
- Upload/ingestion will return `400 Bad Request`
- Error message will indicate supported file types
- Check `DocumentLoaderFactory.SUPPORTED_EXTENSIONS` for supported types

### Index Not Found

If Pinecone index doesn't exist:
- Service will attempt to create index on startup
- If creation fails, service initialization will fail
- Check Pinecone API key and index configuration

---

## Limitations

1. **File Size**: Maximum file size depends on server configuration and memory
2. **Supported Formats**: Only specific file types are supported (see Supported File Extensions)
3. **Chunking**: Large documents are split into chunks, which may lose some context
4. **Namespace Limits**: Pinecone has limits on namespace count and size
5. **Embedding Dimension**: Must match configured dimension (cannot change after index creation)

---

## Future Enhancements

Potential improvements:
- Support for additional file formats (e.g., PowerPoint, Excel)
- Batch ingestion API for multiple files
- Document update/delete operations
- Vector similarity threshold configuration
- Custom metadata extraction
- Document versioning
- Search result ranking customization

