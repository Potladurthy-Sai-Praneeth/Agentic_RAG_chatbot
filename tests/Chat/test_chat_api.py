"""
Comprehensive tests for Chat API endpoints.
Tests all endpoints, authentication, and error scenarios.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime
from Chat.chat_api import app
from Chat.chat_service import ChatService


@pytest.fixture
def mock_chat_service():
    """Create a mock ChatService."""
    service = MagicMock(spec=ChatService)
    service._initialized = True
    return service


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {"user_id": "test_user_12345"}


@pytest.fixture
def client(mock_chat_service):
    """Create a test client with mocked chat service."""
    from fastapi.testclient import TestClient
    from Chat.chat_api import app, get_current_user
    
    # Override the dependency
    async def override_get_current_user():
        return {"user_id": "test_user_12345"}
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Patch the global chat_db
    with patch('Chat.chat_api.chat_db', mock_chat_service):
        yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


class TestChatAPIStoreMessage:
    """Tests for POST /chat/{session_id}/add-message endpoint."""
    
    def test_store_message_success(self, client, mock_chat_service):
        """Test successful message storage."""
        session_id = "test_session_12345"
        message_data = {
            "message_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "user",
            "content": "Hello, this is a test message"
        }
        
        test_timestamp = datetime.now()
        mock_chat_service.store_message = AsyncMock(return_value={
            "message_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": test_timestamp
        })
        
        # Mock authentication
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.post(
                f"/chat/{session_id}/add-message",
                json=message_data,
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert "message_id" in response.json()
        assert response.json()["message_id"] == "550e8400-e29b-41d4-a716-446655440000"
    
    def test_store_message_with_timestamp(self, client, mock_chat_service):
        """Test successful message storage with provided timestamp."""
        session_id = "test_session_12345"
        test_timestamp = datetime.now()
        message_data = {
            "message_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "user",
            "content": "Hello, this is a test message",
            "timestamp": test_timestamp.isoformat()
        }
        
        mock_chat_service.store_message = AsyncMock(return_value={
            "message_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": test_timestamp
        })
        
        # Mock authentication
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.post(
                f"/chat/{session_id}/add-message",
                json=message_data,
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert "message_id" in response.json()
        assert response.json()["message_id"] == "550e8400-e29b-41d4-a716-446655440000"
        # Verify timestamp was passed to service
        mock_chat_service.store_message.assert_called_once()
        call_args = mock_chat_service.store_message.call_args
        assert call_args.kwargs.get('timestamp') is not None
        assert call_args.kwargs.get('message_id') == "550e8400-e29b-41d4-a716-446655440000"
    
    def test_store_message_service_not_initialized(self, client):
        """Test store message when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.post(
                "/chat/test_session/add-message",
                json={"message_id": "550e8400-e29b-41d4-a716-446655440000", "role": "user", "content": "test"},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503
    
    def test_store_message_unauthorized(self, mock_chat_service):
        """Test store message without authentication."""
        from fastapi.testclient import TestClient
        from Chat.chat_api import app, get_current_user
        from fastapi import HTTPException
        
        # Override dependency to raise HTTPException
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('Chat.chat_api.chat_db', mock_chat_service):
            client = TestClient(app)
            response = client.post(
                "/chat/test_session/add-message",
                json={"message_id": "550e8400-e29b-41d4-a716-446655440000", "role": "user", "content": "test"}
            )
        
        app.dependency_overrides.clear()
        assert response.status_code == 401


class TestChatAPIGetMessages:
    """Tests for GET /chat/{session_id}/get-messages endpoint."""
    
    def test_get_messages_success(self, client, mock_chat_service):
        """Test successful message retrieval."""
        session_id = "test_session_12345"
        
        mock_messages = [
            {
                "message_id": "msg_1",
                "role": "user",
                "content": "Hello",
                "timestamp": datetime.now()
            },
            {
                "message_id": "msg_2",
                "role": "assistant",
                "content": "Hi there",
                "timestamp": datetime.now()
            }
        ]
        
        mock_chat_service.get_messages = AsyncMock(return_value=mock_messages)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-messages",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["role"] == "user"
    
    def test_get_messages_empty(self, client, mock_chat_service):
        """Test get messages when no messages exist."""
        session_id = "test_session_12345"
        
        mock_chat_service.get_messages = AsyncMock(return_value=[])
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-messages",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_messages_service_not_initialized(self, client):
        """Test get messages when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.get(
                "/chat/test_session/get-messages",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestChatAPIGetSummary:
    """Tests for GET /chat/{session_id}/get-summary endpoint."""
    
    def test_get_summary_success(self, client, mock_chat_service):
        """Test successful summary retrieval."""
        session_id = "test_session_12345"
        
        mock_summary = {
            "session_id": session_id,
            "user_id": "test_user_12345",
            "summary": "This is a test summary",
            "last_updated": datetime.now(),
            "message_count": 10
        }
        
        mock_chat_service.get_summary = AsyncMock(return_value=mock_summary)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-summary",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["summary"] == "This is a test summary"
    
    def test_get_summary_not_found(self, client, mock_chat_service):
        """Test get summary when summary doesn't exist."""
        session_id = "test_session_12345"
        
        mock_chat_service.get_summary = AsyncMock(return_value=None)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-summary",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 404
    
    def test_get_summary_service_not_initialized(self, client):
        """Test get summary when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.get(
                "/chat/test_session/get-summary",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestChatAPIInsertSummary:
    """Tests for POST /chat/{session_id}/insert-summary endpoint."""
    
    def test_insert_summary_success(self, client, mock_chat_service):
        """Test successful summary insertion."""
        session_id = "test_session_12345"
        summary_data = {
            "summary": "This is a test summary",
            "message_count": 10
        }
        
        mock_chat_service.insert_summary = AsyncMock(return_value=True)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.post(
                f"/chat/{session_id}/insert-summary",
                json=summary_data,
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_insert_summary_with_timestamp(self, client, mock_chat_service):
        """Test successful summary insertion with provided timestamp."""
        session_id = "test_session_12345"
        test_timestamp = datetime.now()
        summary_data = {
            "summary": "This is a test summary",
            "message_count": 10,
            "timestamp": test_timestamp.isoformat()
        }
        
        mock_chat_service.insert_summary = AsyncMock(return_value=True)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.post(
                f"/chat/{session_id}/insert-summary",
                json=summary_data,
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        # Verify timestamp was passed to service
        mock_chat_service.insert_summary.assert_called_once()
        call_args = mock_chat_service.insert_summary.call_args
        assert call_args.kwargs.get('timestamp') is not None
    
    def test_insert_summary_service_not_initialized(self, client):
        """Test insert summary when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.post(
                "/chat/test_session/insert-summary",
                json={"summary": "test", "message_count": 5},
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestChatAPIGetMessageCount:
    """Tests for GET /chat/{session_id}/get-message-count endpoint."""
    
    def test_get_message_count_success(self, client, mock_chat_service):
        """Test successful message count retrieval."""
        session_id = "test_session_12345"
        
        mock_chat_service.get_message_count = AsyncMock(return_value=5)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-message-count",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["message_count"] == 5
        assert response.json()["session_id"] == session_id
    
    def test_get_message_count_zero(self, client, mock_chat_service):
        """Test get message count when no messages exist."""
        session_id = "test_session_12345"
        
        mock_chat_service.get_message_count = AsyncMock(return_value=0)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.get(
                f"/chat/{session_id}/get-message-count",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["message_count"] == 0
    
    def test_get_message_count_service_not_initialized(self, client):
        """Test get message count when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.get(
                "/chat/test_session/get-message-count",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestChatAPIDeleteSession:
    """Tests for DELETE /chat/{session_id}/delete endpoint."""
    
    def test_delete_session_success(self, client, mock_chat_service):
        """Test successful session deletion."""
        session_id = "test_session_12345"
        
        mock_chat_service.delete_session = AsyncMock(return_value=True)
        
        with patch('Chat.chat_api.get_current_user', return_value={"user_id": "test_user_12345"}):
            response = client.delete(
                f"/chat/{session_id}/delete",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    def test_delete_session_service_not_initialized(self, client):
        """Test delete session when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.delete(
                "/chat/test_session/delete",
                headers={"Authorization": "Bearer test_token"}
            )
        
        assert response.status_code == 503


class TestChatAPIHealthCheck:
    """Tests for GET /health endpoint."""
    
    def test_health_check_success(self, client, mock_chat_service):
        """Test successful health check."""
        mock_chat_service.health_check = AsyncMock(return_value=True)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_check_service_not_initialized(self, client):
        """Test health check when service is not initialized."""
        with patch('Chat.chat_api.chat_db', None):
            response = client.get("/health")
        
        assert response.status_code == 503
    
    def test_health_check_unhealthy(self, client, mock_chat_service):
        """Test health check when database is unhealthy."""
        mock_chat_service.health_check = AsyncMock(return_value=False)
        
        response = client.get("/health")
        
        assert response.status_code == 503


class TestChatAPIRoot:
    """Tests for GET / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["service"] == "Chat Service API"
        assert response.json()["status"] == "running"

