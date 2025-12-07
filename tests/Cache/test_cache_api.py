"""
Comprehensive tests for Cache API endpoints.
Tests all endpoints, authentication, and error scenarios.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime
from Cache.cache_api import app
from Cache.cache_service import RedisService


@pytest.fixture
def mock_cache_service():
    """Create a mock RedisService."""
    service = MagicMock(spec=RedisService)
    service._initialized = True
    return service


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {"user_id": "test_user_12345"}


@pytest.fixture
def client(mock_cache_service):
    """Create a test client with mocked cache service."""
    from fastapi.testclient import TestClient
    from Cache.cache_api import app
    from Cache.jwt_utils import get_current_user, verify_token
    
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
    
    # Patch verify_token in the middleware
    with patch('Cache.cache_api.cache', mock_cache_service), \
         patch('Cache.cache_api.verify_token', mock_verify_token):
        yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


class TestCacheAPIAddMessage:
    """Tests for POST /cache/{session_id}/message endpoint."""
    
    def test_add_message_success(self, client, mock_cache_service):
        """Test successful message addition."""
        session_id = "test_session_12345"
        message_data = {
            "role": "user",
            "content": "Hello, this is a test message"
        }
        
        mock_cache_service.add_message = MagicMock(return_value=False)
        
        response = client.post(
            f"/cache/{session_id}/message",
            json=message_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["message"] == "Message added successfully"
        assert response.json()["needs_summarization"] is False
    
    def test_add_message_needs_summarization(self, client, mock_cache_service):
        """Test message addition when summarization is needed."""
        session_id = "test_session_12345"
        message_data = {
            "role": "user",
            "content": "Hello, this is a test message"
        }
        
        mock_cache_service.add_message = MagicMock(return_value=True)
        
        response = client.post(
            f"/cache/{session_id}/message",
            json=message_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 201
        assert response.json()["needs_summarization"] is True
    
    def test_add_message_service_not_initialized(self, client):
        """Test add message when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.post(
                "/cache/test_session/message",
                json={"role": "user", "content": "test"},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_add_message_unauthorized(self, mock_cache_service):
        """Test add message without authentication."""
        from fastapi.testclient import TestClient
        from Cache.cache_api import app
        from Cache.jwt_utils import get_current_user
        
        # Override dependency to raise HTTPException
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('Cache.cache_api.cache', mock_cache_service):
            client = TestClient(app)
            response = client.post(
                "/cache/test_session/message",
                json={"role": "user", "content": "test"}
            )
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_add_message_service_error(self, client, mock_cache_service):
        """Test add message when service raises error."""
        session_id = "test_session_12345"
        message_data = {
            "role": "user",
            "content": "Hello, this is a test message"
        }
        
        mock_cache_service.add_message = MagicMock(side_effect=Exception("Service error"))
        
        response = client.post(
            f"/cache/{session_id}/message",
            json=message_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestCacheAPIGetMessages:
    """Tests for GET /cache/{session_id}/messages endpoint."""
    
    def test_get_messages_success(self, client, mock_cache_service):
        """Test successful message retrieval."""
        session_id = "test_session_12345"
        
        mock_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        mock_cache_service.get_messages = MagicMock(return_value=mock_messages)
        
        response = client.get(
            f"/cache/{session_id}/messages",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["role"] == "user"
        assert response.json()[1]["role"] == "assistant"
    
    def test_get_messages_with_limit(self, client, mock_cache_service):
        """Test get messages with limit parameter."""
        session_id = "test_session_12345"
        
        mock_messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        mock_cache_service.get_messages = MagicMock(return_value=mock_messages)
        
        response = client.get(
            f"/cache/{session_id}/messages?limit=1",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        # Verify limit was passed to service
        mock_cache_service.get_messages.assert_called_once_with(session_id, 1)
    
    def test_get_messages_empty(self, client, mock_cache_service):
        """Test get messages when no messages exist."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_messages = MagicMock(return_value=[])
        
        response = client.get(
            f"/cache/{session_id}/messages",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_messages_service_not_initialized(self, client):
        """Test get messages when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.get(
                "/cache/test_session/messages",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_get_messages_service_error(self, client, mock_cache_service):
        """Test get messages when service raises error."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_messages = MagicMock(side_effect=Exception("Service error"))
        
        response = client.get(
            f"/cache/{session_id}/messages",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestCacheAPIGetMessageCount:
    """Tests for GET /cache/{session_id}/message_count endpoint."""
    
    def test_get_message_count_success(self, client, mock_cache_service):
        """Test successful message count retrieval."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_message_count = MagicMock(return_value=5)
        
        response = client.get(
            f"/cache/{session_id}/message_count",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["count"] == 5
    
    def test_get_message_count_zero(self, client, mock_cache_service):
        """Test get message count when no messages exist."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_message_count = MagicMock(return_value=0)
        
        response = client.get(
            f"/cache/{session_id}/message_count",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["count"] == 0
    
    def test_get_message_count_service_not_initialized(self, client):
        """Test get message count when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.get(
                "/cache/test_session/message_count",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestCacheAPITrimCache:
    """Tests for DELETE /cache/{session_id}/trim endpoint."""
    
    def test_trim_cache_success(self, client, mock_cache_service):
        """Test successful cache trimming."""
        session_id = "test_session_12345"
        
        mock_cache_service.trim_cache = MagicMock(return_value=True)
        
        response = client.delete(
            f"/cache/{session_id}/trim?keep_last=10",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Cache trimmed successfully"
        assert response.json()["success"] is True
    
    def test_trim_cache_no_trim_needed(self, client, mock_cache_service):
        """Test trim cache when trimming is not needed."""
        session_id = "test_session_12345"
        
        mock_cache_service.trim_cache = MagicMock(return_value=False)
        
        response = client.delete(
            f"/cache/{session_id}/trim?keep_last=10",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is False
    
    def test_trim_cache_without_keep_last(self, client, mock_cache_service):
        """Test trim cache without keep_last parameter."""
        session_id = "test_session_12345"
        
        mock_cache_service.trim_cache = MagicMock(return_value=False)
        
        response = client.delete(
            f"/cache/{session_id}/trim",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
    
    def test_trim_cache_service_not_initialized(self, client):
        """Test trim cache when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.delete(
                "/cache/test_session/trim?keep_last=10",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestCacheAPIUpdateSummary:
    """Tests for POST /cache/{session_id}/update-summary endpoint."""
    
    def test_update_summary_success(self, client, mock_cache_service):
        """Test successful summary update."""
        session_id = "test_session_12345"
        summary_data = {
            "summary": "This is a test summary"
        }
        
        mock_cache_service.update_summary = MagicMock(return_value=True)
        
        response = client.post(
            f"/cache/{session_id}/update-summary",
            json=summary_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Session summary updated successfully"
        assert response.json()["success"] is True
    
    def test_update_summary_service_not_initialized(self, client):
        """Test update summary when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.post(
                "/cache/test_session/update-summary",
                json={"summary": "test"},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_update_summary_service_error(self, client, mock_cache_service):
        """Test update summary when service raises error."""
        session_id = "test_session_12345"
        summary_data = {
            "summary": "This is a test summary"
        }
        
        mock_cache_service.update_summary = MagicMock(side_effect=Exception("Service error"))
        
        response = client.post(
            f"/cache/{session_id}/update-summary",
            json=summary_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestCacheAPIGetSummary:
    """Tests for GET /cache/{session_id}/get-summary endpoint."""
    
    def test_get_summary_success(self, client, mock_cache_service):
        """Test successful summary retrieval."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_summary = MagicMock(return_value="This is a test summary")
        
        response = client.get(
            f"/cache/{session_id}/get-summary",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["summary"] == "This is a test summary"
        assert response.json()["success"] is True
    
    def test_get_summary_not_found(self, client, mock_cache_service):
        """Test get summary when summary doesn't exist."""
        session_id = "test_session_12345"
        
        mock_cache_service.get_summary = MagicMock(return_value=None)
        
        response = client.get(
            f"/cache/{session_id}/get-summary",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["summary"] is None
        assert response.json()["success"] is True
    
    def test_get_summary_service_not_initialized(self, client):
        """Test get summary when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.get(
                "/cache/test_session/get-summary",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestCacheAPIClearCache:
    """Tests for DELETE /cache/{session_id}/clear endpoint."""
    
    def test_clear_cache_success(self, client, mock_cache_service):
        """Test successful cache clearing."""
        session_id = "test_session_12345"
        
        mock_cache_service.clear_session = MagicMock(return_value=True)
        
        response = client.delete(
            f"/cache/{session_id}/clear",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Cache cleared successfully"
        assert response.json()["success"] is True
    
    def test_clear_cache_service_not_initialized(self, client):
        """Test clear cache when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.delete(
                "/cache/test_session/clear",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_clear_cache_service_error(self, client, mock_cache_service):
        """Test clear cache when service raises error."""
        session_id = "test_session_12345"
        
        mock_cache_service.clear_session = MagicMock(side_effect=Exception("Service error"))
        
        response = client.delete(
            f"/cache/{session_id}/clear",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 500


class TestCacheAPIHealthCheck:
    """Tests for GET /health endpoint."""
    
    def test_health_check_success(self, client, mock_cache_service):
        """Test successful health check."""
        mock_cache_service.health_check = MagicMock(return_value=True)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert "details" in response.json()
    
    def test_health_check_service_not_initialized(self, client):
        """Test health check when service is not initialized."""
        with patch('Cache.cache_api.cache', None):
            response = client.get("/health")
        
        assert response.status_code == 503
    
    def test_health_check_unhealthy(self, client, mock_cache_service):
        """Test health check when cache is unhealthy."""
        mock_cache_service.health_check = MagicMock(return_value=False)
        
        response = client.get("/health")
        
        assert response.status_code == 500
    
    def test_health_check_service_error(self, client, mock_cache_service):
        """Test health check when service raises error."""
        mock_cache_service.health_check = MagicMock(side_effect=Exception("Service error"))
        
        response = client.get("/health")
        
        assert response.status_code == 500


class TestCacheAPIRoot:
    """Tests for GET / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["service"] == "Cache Service API"
        assert response.json()["status"] == "running"
        assert "endpoints" in response.json()


class TestCacheAPIAuthentication:
    """Tests for authentication scenarios."""
    
    def test_all_endpoints_require_auth(self, mock_cache_service):
        """Test that all endpoints require authentication."""
        from fastapi.testclient import TestClient
        from Cache.cache_api import app
        from Cache.jwt_utils import get_current_user
        
        # Override dependency to raise HTTPException
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('Cache.cache_api.cache', mock_cache_service):
            client = TestClient(app)
            
            # Test all endpoints require auth
            endpoints = [
                ("POST", "/cache/test_session/message", {"role": "user", "content": "test"}),
                ("GET", "/cache/test_session/messages", None),
                ("GET", "/cache/test_session/message_count", None),
                ("DELETE", "/cache/test_session/trim?keep_last=10", None),
                ("POST", "/cache/test_session/update-summary", {"summary": "test"}),
                ("GET", "/cache/test_session/get-summary", None),
                ("DELETE", "/cache/test_session/clear", None),
            ]
            
            for method, endpoint, data in endpoints:
                if method == "POST":
                    response = client.post(endpoint, json=data)
                elif method == "GET":
                    response = client.get(endpoint)
                elif method == "DELETE":
                    response = client.delete(endpoint)
                
                assert response.status_code == 401, f"{method} {endpoint} should require auth"
        
        app.dependency_overrides.clear()
    
    def test_health_check_no_auth_required(self, client, mock_cache_service):
        """Test that health check doesn't require authentication."""
        mock_cache_service.health_check = MagicMock(return_value=True)
        
        # No Authorization header
        response = client.get("/health")
        
        assert response.status_code == 200
    
    def test_root_no_auth_required(self, client):
        """Test that root endpoint doesn't require authentication."""
        # No Authorization header
        response = client.get("/")
        
        assert response.status_code == 200

