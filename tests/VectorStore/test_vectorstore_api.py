"""
Comprehensive tests for VectorStore API endpoints.
Tests all endpoints, authentication, and error scenarios.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
import io

from VectorStore.vectorstore_api import app
from VectorStore.vectorstore_service import PineconeService
from tests.VectorStore.conftest import *


@pytest.fixture
def mock_pinecone_service():
    """Create a mock PineconeService."""
    service = MagicMock(spec=PineconeService)
    service.pinecone_index_name = "test_index"
    service.client = MagicMock()
    return service


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {"user_id": "test_user_12345"}


@pytest.fixture
def client(mock_pinecone_service):
    """Create a test client with mocked service."""
    from VectorStore.jwt_utils import get_current_user, verify_token
    
    # Mock verify_token to return a valid payload for test tokens
    def mock_verify_token(token: str):
        """Mock verify_token to return valid payload for test tokens."""
        return {
            "sub": "test_user_12345",
            "type": "access",
            "exp": 9999999999,
            "iat": 1000000000
        }
    
    # Override the dependency
    async def override_get_current_user():
        return {"user_id": "test_user_12345"}
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Patch verify_token in the middleware and the global service
    with patch('VectorStore.vectorstore_api.pinecone_service', mock_pinecone_service), \
         patch('VectorStore.vectorstore_api.verify_token', mock_verify_token):
        yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


class TestVectorStoreAPIIndexManagement:
    """Tests for index management endpoints."""
    
    def test_get_index_stats_success(self, client, mock_pinecone_service):
        """Test successful index stats retrieval."""
        mock_pinecone_service.get_index_stats = MagicMock(return_value={
            'total_vector_count': 100,
            'namespaces': {'namespace1': {'vector_count': 50}},
            'dimension': 768,
            'index_name': 'test_index'
        })
        
        response = client.get(
            "/vectorstore/index/stats",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["total_vector_count"] == 100
        assert response.json()["success"] is True
    
    def test_get_index_stats_service_not_initialized(self, client):
        """Test get index stats when service is not initialized."""
        with patch('VectorStore.vectorstore_api.pinecone_service', None):
            response = client.get(
                "/vectorstore/index/stats",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_get_index_stats_unauthorized(self, mock_pinecone_service):
        """Test get index stats without authentication."""
        from VectorStore.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('VectorStore.vectorstore_api.pinecone_service', mock_pinecone_service):
            client = TestClient(app)
            response = client.get("/vectorstore/index/stats")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401


class TestVectorStoreAPIUploadS3:
    """Tests for S3 upload endpoints."""
    
    def test_generate_presigned_url_success(self, client, mock_pinecone_service):
        """Test successful presigned URL generation."""
        mock_pinecone_service.generate_s3_upload_url = MagicMock(return_value={
            'presigned_url': 'https://s3.amazonaws.com/bucket/key?presigned=...',
            's3_key': 'uploads/user123/20240101/uuid.pdf',
            'expires_in': 3600,
            'bucket': 'test_bucket',
            'file_name': 'test.pdf'
        })
        
        response = client.post(
            "/vectorstore/presigned-url",
            json={
                "file_name": "test.pdf",
                "expiration": 3600
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "presigned_url" in response.json()
    
    def test_generate_presigned_url_s3_not_configured(self, client, mock_pinecone_service):
        """Test presigned URL generation when S3 is not configured."""
        mock_pinecone_service.generate_s3_upload_url = MagicMock(side_effect=ValueError("S3 is not configured"))
        
        response = client.post(
            "/vectorstore/presigned-url",
            json={"file_name": "test.pdf"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 400

    
    def test_process_s3_upload_success(self, client, mock_pinecone_service):
        """Test successful S3 upload processing."""
        mock_pinecone_service.ingest_from_s3_key = MagicMock(return_value={
            'total_files': 1,
            'total_documents': 1,
            'total_chunks': 5,
            'success': True,
            'namespace': 'test_namespace'
        })
        
        response = client.post(
            "/vectorstore/process-s3-upload",
            json={
                "s3_key": "uploads/file.pdf",
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert response.json()["total_chunks"] == 5


class TestVectorStoreAPIUploadLocal:
    """Tests for local upload endpoints."""
    
    def test_upload_file_success(self, client, mock_pinecone_service):
        """Test successful file upload."""
        mock_pinecone_service.ingest_from_file_content = MagicMock(return_value={
            'total_files': 1,
            'total_documents': 1,
            'total_chunks': 3,
            'success': True,
            'namespace': None
        })
        
        file_content = b"This is test file content"
        response = client.post(
            "/vectorstore/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            data={"namespace": "test_namespace"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert response.json()["total_chunks"] == 3
    
    def test_upload_zip_file(self, client, mock_pinecone_service, sample_zip_file):
        """Test uploading a zip file."""
        mock_pinecone_service.ingest_from_file_content = MagicMock(return_value={
            'total_files': 2,
            'total_documents': 2,
            'total_chunks': 4,
            'success': True,
            'namespace': None
        })
        
        response = client.post(
            "/vectorstore/upload",
            files={"file": ("test.zip", io.BytesIO(sample_zip_file), "application/zip")},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["total_files"] == 2
    
    def test_upload_file_service_not_initialized(self, client):
        """Test upload when service is not initialized."""
        with patch('VectorStore.vectorstore_api.pinecone_service', None):
            response = client.post(
                "/vectorstore/upload",
                files={"file": ("test.txt", io.BytesIO(b"test"), "text/plain")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_upload_file_invalid_file_type(self, client, mock_pinecone_service):
        """Test upload with unsupported file type."""
        mock_pinecone_service.ingest_from_file_content = MagicMock(side_effect=ValueError("Unsupported file type"))
        
        response = client.post(
            "/vectorstore/upload",
            files={"file": ("test.xyz", io.BytesIO(b"test"), "application/octet-stream")},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 400


class TestVectorStoreAPIIngestion:
    """Tests for ingestion endpoints."""
    
    def test_ingest_documents_local_path(self, client, mock_pinecone_service):
        """Test ingestion from local path."""
        mock_pinecone_service.ingest_documents = MagicMock(return_value={
            'total_files': 1,
            'total_documents': 1,
            'total_chunks': 2,
            'success': True,
            'namespace': 'test_namespace'
        })
        
        response = client.post(
            "/vectorstore/ingest",
            json={
                "source": "/path/to/file.pdf",
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
    
    def test_ingest_documents_s3_url(self, client, mock_pinecone_service):
        """Test ingestion from S3 presigned URL."""
        mock_pinecone_service.ingest_documents = MagicMock(return_value={
            'total_files': 1,
            'total_documents': 1,
            'total_chunks': 2,
            'success': True,
            'namespace': None
        })
        
        response = client.post(
            "/vectorstore/ingest",
            json={
                "source": "https://s3.amazonaws.com/bucket/file.pdf?presigned=...",
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
    
    def test_ingest_documents_file_not_found(self, client, mock_pinecone_service):
        """Test ingestion when file is not found."""
        mock_pinecone_service.ingest_documents = MagicMock(side_effect=FileNotFoundError("File not found"))
        
        response = client.post(
            "/vectorstore/ingest",
            json={
                "source": "/nonexistent/file.pdf",
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 404
    
    def test_ingest_documents_invalid_source(self, client, mock_pinecone_service):
        """Test ingestion with invalid source."""
        mock_pinecone_service.ingest_documents = MagicMock(side_effect=ValueError("Invalid source"))
        
        response = client.post(
            "/vectorstore/ingest",
            json={
                "source": "invalid://source",
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 400


class TestVectorStoreAPISearch:
    """Tests for search endpoints."""
    
    def test_search_success(self, client, mock_pinecone_service):
        """Test successful search."""
        from langchain_core.documents import Document
        
        mock_documents = [
            Document(page_content="Test content 1", metadata={"source": "test1.pdf"}),
            Document(page_content="Test content 2", metadata={"source": "test2.pdf"})
        ]
        
        mock_pinecone_service.search = MagicMock(return_value=mock_documents)
        
        response = client.post(
            "/vectorstore/search",
            json={
                "query": "test query",
                "top_k": 5,
                "namespace": "test_namespace"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["total_results"] == 2
        assert len(response.json()["results"]) == 2
    
    def test_search_with_filter(self, client, mock_pinecone_service):
        """Test search with metadata filter."""
        from langchain_core.documents import Document
        
        mock_documents = [
            Document(page_content="Test content", metadata={"source_file": "test.pdf"})
        ]
        
        mock_pinecone_service.search = MagicMock(return_value=mock_documents)
        
        response = client.post(
            "/vectorstore/search",
            json={
                "query": "test query",
                "top_k": 5,
                "namespace": "test_namespace",
                "filter": {"source_file": "test.pdf"}
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        call_args = mock_pinecone_service.search.call_args
        assert call_args[1]['filter'] == {"source_file": "test.pdf"}
    
    def test_search_without_top_k(self, client, mock_pinecone_service):
        """Test search without specifying top_k."""
        from langchain_core.documents import Document
        
        mock_documents = [Document(page_content="Test content", metadata={})]
        mock_pinecone_service.search = MagicMock(return_value=mock_documents)
        
        response = client.post(
            "/vectorstore/search",
            json={
                "query": "test query"
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
    
    def test_search_service_not_initialized(self, client):
        """Test search when service is not initialized."""
        with patch('VectorStore.vectorstore_api.pinecone_service', None):
            response = client.post(
                "/vectorstore/search",
                json={"query": "test query"},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_search_error(self, client, mock_pinecone_service):
        """Test search when error occurs."""
        mock_pinecone_service.search = MagicMock(side_effect=Exception("Search error"))
        
        response = client.post(
            "/vectorstore/search",
            json={"query": "test query"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestVectorStoreAPINamespaceManagement:
    """Tests for namespace management endpoints."""
    
    def test_delete_namespace_success(self, client, mock_pinecone_service):
        """Test successful namespace deletion."""
        mock_pinecone_service.delete_namespace = MagicMock(return_value=True)
        
        response = client.delete(
            "/vectorstore/namespace/test_namespace",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["namespace"] == "test_namespace"
    
    def test_delete_namespace_service_not_initialized(self, client):
        """Test delete namespace when service is not initialized."""
        with patch('VectorStore.vectorstore_api.pinecone_service', None):
            response = client.delete(
                "/vectorstore/namespace/test_namespace",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_delete_namespace_error(self, client, mock_pinecone_service):
        """Test delete namespace when error occurs."""
        mock_pinecone_service.delete_namespace = MagicMock(side_effect=Exception("Delete error"))
        
        response = client.delete(
            "/vectorstore/namespace/test_namespace",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestVectorStoreAPIHealthCheck:
    """Tests for health check endpoints."""
    
    def test_health_check_success(self, client, mock_pinecone_service):
        """Test successful health check."""
        mock_index_info = MagicMock()
        mock_index_info.status = {'state': 'Ready'}
        mock_pinecone_service.client.describe_index = MagicMock(return_value=mock_index_info)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_check_service_not_initialized(self, client):
        """Test health check when service is not initialized."""
        with patch('VectorStore.vectorstore_api.pinecone_service', None):
            response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
    
    def test_health_check_error(self, client, mock_pinecone_service):
        """Test health check when error occurs."""
        mock_pinecone_service.client.describe_index = MagicMock(side_effect=Exception("Health check error"))
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"


class TestVectorStoreAPIRoot:
    """Tests for root endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["service"] == "VectorStore Service API"
        assert response.json()["status"] == "running"
        assert "endpoints" in response.json()


class TestVectorStoreAPIAuthentication:
    """Tests for authentication scenarios."""
    
    def test_all_endpoints_require_auth(self, mock_pinecone_service):
        """Test that all endpoints require authentication."""
        from VectorStore.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('VectorStore.vectorstore_api.pinecone_service', mock_pinecone_service):
            client = TestClient(app)
            
            # Test all endpoints require auth
            endpoints = [
                ("GET", "/vectorstore/index/stats", None),
                ("POST", "/vectorstore/presigned-url", {"file_name": "test.pdf"}),
                ("POST", "/vectorstore/upload", None),
                ("POST", "/vectorstore/process-s3-upload", {"s3_key": "test.pdf"}),
                ("POST", "/vectorstore/ingest", {"source": "/path/to/file.pdf"}),
                ("POST", "/vectorstore/search", {"query": "test"}),
                ("DELETE", "/vectorstore/namespace/test", None),
            ]
            
            for method, endpoint, data in endpoints:
                if method == "POST":
                    if endpoint == "/vectorstore/upload":
                        response = client.post(endpoint, files={"file": ("test.txt", io.BytesIO(b"test"), "text/plain")})
                    else:
                        response = client.post(endpoint, json=data)
                elif method == "GET":
                    response = client.get(endpoint)
                elif method == "DELETE":
                    response = client.delete(endpoint)
                
                assert response.status_code == 401, f"{method} {endpoint} should require auth"
        
        app.dependency_overrides.clear()
    
    def test_health_check_no_auth_required(self, client, mock_pinecone_service):
        """Test that health check doesn't require authentication."""
        mock_index_info = MagicMock()
        mock_index_info.status = {'state': 'Ready'}
        mock_pinecone_service.client.describe_index = MagicMock(return_value=mock_index_info)
        
        # No Authorization header
        response = client.get("/health")
        
        assert response.status_code == 200
    
    def test_root_no_auth_required(self, client):
        """Test that root endpoint doesn't require authentication."""
        # No Authorization header
        response = client.get("/")
        
        assert response.status_code == 200

