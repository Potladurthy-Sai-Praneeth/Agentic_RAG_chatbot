"""
Comprehensive tests for RAG API endpoints.
Tests all endpoints, authentication, and error scenarios.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime
from RAG.rag_api import app
from RAG.rag_service import RAGService
from RAG.jwt_utils import get_current_user, verify_token


class TestRAGAPIGetSessionMessages:
    """Tests for GET /rag/{session_id}/get-session-messages endpoint."""
    
    def test_get_session_messages_success(self, client, mock_rag_service, sample_chat_messages):
        """Test successful retrieval of session messages."""
        mock_rag_service.get_session_messages = AsyncMock(return_value=sample_chat_messages)
        
        token = "test_token"
        
        response = client.get(
            "/rag/test_session_12345/get-session-messages",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 2
        mock_rag_service.get_session_messages.assert_called_once_with("test_session_12345")
    
    def test_get_session_messages_empty(self, client, mock_rag_service):
        """Test get session messages when session has no messages."""
        mock_rag_service.get_session_messages = AsyncMock(return_value=[])
        
        token = "test_token"
        
        response = client.get(
            "/rag/test_session_12345/get-session-messages",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_session_messages_service_not_initialized(self, client):
        """Test get session messages when service is not initialized."""
        token = "test_token"
        
        with patch('RAG.rag_api.rag', None):
            response = client.get(
                "/rag/test_session_12345/get-session-messages",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_get_session_messages_unauthorized(self, mock_rag_service):
        """Test get session messages without authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            response = client.get("/rag/test_session_12345/get-session-messages")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_get_session_messages_service_error(self, client, mock_rag_service):
        """Test get session messages when service raises error."""
        mock_rag_service.get_session_messages = AsyncMock(side_effect=Exception("Database error"))
        
        token = "test_token"
        
        response = client.get(
            "/rag/test_session_12345/get-session-messages",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestRAGAPIChat:
    """Tests for POST /rag/{session_id}/chat endpoint."""
    
    def test_chat_success(self, client, mock_rag_service):
        """Test successful chat interaction."""
        user_message = {
            "message_id": "test_msg_123",
            "role": "user",
            "content": "Hello, how are you?",
            "timestamp": datetime.now().isoformat(),
            "is_first_message": False
        }
        
        mock_rag_service.store_message = AsyncMock(return_value={"success": True})
        mock_rag_service.chat = AsyncMock(return_value="I'm doing well, thank you!")
        mock_rag_service.set_session_title = AsyncMock(return_value={"success": True, "message": "Title set"})
        
        token = "test_token"
        
        response = client.post(
            "/rag/test_session_12345/chat",
            json=user_message,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "response" in response.json()
        assert "message_id" in response.json()
        assert mock_rag_service.store_message.call_count == 2  # User message + assistant response
        assert mock_rag_service.chat.called
    
    def test_chat_first_message_sets_title(self, client, mock_rag_service):
        """Test that first message sets session title."""
        user_message = {
            "message_id": "test_msg_123",
            "role": "user",
            "content": "Hello, how are you?",
            "timestamp": datetime.now().isoformat(),
            "is_first_message": True
        }
        
        mock_rag_service.store_message = AsyncMock(return_value={"success": True})
        mock_rag_service.chat = AsyncMock(return_value="I'm doing well, thank you!")
        mock_rag_service.set_session_title = AsyncMock(return_value={"success": True, "message": "Title set"})
        
        token = "test_token"
        
        response = client.post(
            "/rag/test_session_12345/chat",
            json=user_message,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert mock_rag_service.set_session_title.called
    
    def test_chat_service_not_initialized(self, client):
        """Test chat when service is not initialized."""
        user_message = {
            "message_id": "test_msg_123",
            "role": "user",
            "content": "Hello",
            "timestamp": datetime.now().isoformat()
        }
        
        token = "test_token"
        
        with patch('RAG.rag_api.rag', None):
            response = client.post(
                "/rag/test_session_12345/chat",
                json=user_message,
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_chat_unauthorized(self, mock_rag_service):
        """Test chat without authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            response = client.post(
                "/rag/test_session_12345/chat",
                json={"message_id": "test", "role": "user", "content": "Hello"}
            )
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_chat_service_error(self, client, mock_rag_service):
        """Test chat when service raises error."""
        user_message = {
            "message_id": "test_msg_123",
            "role": "user",
            "content": "Hello",
            "timestamp": datetime.now().isoformat()
        }
        
        mock_rag_service.store_message = AsyncMock(side_effect=Exception("Database error"))
        
        token = "test_token"
        
        response = client.post(
            "/rag/test_session_12345/chat",
            json=user_message,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestRAGAPIGetSessions:
    """Tests for GET /rag/get-sessions endpoint."""
    
    def test_get_sessions_success(self, client, mock_rag_service, sample_sessions):
        """Test successful retrieval of user sessions."""
        mock_rag_service.get_sessions = AsyncMock(return_value=sample_sessions)
        
        token = "test_token"
        
        response = client.get(
            "/rag/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 2
    
    def test_get_sessions_empty(self, client, mock_rag_service):
        """Test get sessions when user has no sessions."""
        mock_rag_service.get_sessions = AsyncMock(return_value=[])
        
        token = "test_token"
        
        response = client.get(
            "/rag/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_sessions_service_not_initialized(self, client):
        """Test get sessions when service is not initialized."""
        token = "test_token"
        
        with patch('RAG.rag_api.rag', None):
            response = client.get(
                "/rag/get-sessions",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_get_sessions_unauthorized(self, mock_rag_service):
        """Test get sessions without authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            response = client.get("/rag/get-sessions")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_get_sessions_service_error(self, client, mock_rag_service):
        """Test get sessions when service raises error."""
        mock_rag_service.get_sessions = AsyncMock(side_effect=Exception("Database error"))
        
        token = "test_token"
        
        response = client.get(
            "/rag/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestRAGAPICreateSession:
    """Tests for POST /rag/create-session endpoint."""
    
    def test_create_session_success(self, client, mock_rag_service):
        """Test successful session creation."""
        new_session = {
            "session_id": "new_session_123",
            "created_at": datetime.now()
        }
        
        mock_rag_service.create_session = AsyncMock(return_value=new_session)
        
        token = "test_token"
        
        response = client.post(
            "/rag/create-session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["session_id"] == "new_session_123"
        assert "created_at" in response.json()
    
    def test_create_session_service_not_initialized(self, client):
        """Test create session when service is not initialized."""
        token = "test_token"
        
        with patch('RAG.rag_api.rag', None):
            response = client.post(
                "/rag/create-session",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_create_session_unauthorized(self, mock_rag_service):
        """Test create session without authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            response = client.post("/rag/create-session")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_create_session_service_error(self, client, mock_rag_service):
        """Test create session when service raises error."""
        mock_rag_service.create_session = AsyncMock(side_effect=Exception("Database error"))
        
        token = "test_token"
        
        response = client.post(
            "/rag/create-session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestRAGAPIDeleteSession:
    """Tests for DELETE /rag/{session_id}/delete-session endpoint."""
    
    def test_delete_session_success(self, client, mock_rag_service):
        """Test successful session deletion."""
        delete_result = {
            "success": True,
            "message": "Session deleted successfully"
        }
        
        mock_rag_service.delete_session = AsyncMock(return_value=delete_result)
        
        token = "test_token"
        
        response = client.delete(
            "/rag/test_session_12345/delete-session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_rag_service.delete_session.assert_called_once_with("test_user_12345", "test_session_12345")
    
    def test_delete_session_service_not_initialized(self, client):
        """Test delete session when service is not initialized."""
        token = "test_token"
        
        with patch('RAG.rag_api.rag', None):
            response = client.delete(
                "/rag/test_session_12345/delete-session",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_delete_session_unauthorized(self, mock_rag_service):
        """Test delete session without authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            response = client.delete("/rag/test_session_12345/delete-session")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_delete_session_service_error(self, client, mock_rag_service):
        """Test delete session when service raises error."""
        mock_rag_service.delete_session = AsyncMock(side_effect=Exception("Database error"))
        
        token = "test_token"
        
        response = client.delete(
            "/rag/test_session_12345/delete-session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestRAGAPIHealthCheck:
    """Tests for GET /health endpoint."""
    
    def test_health_check_success(self, client, mock_rag_service):
        """Test successful health check."""
        health_status = {
            "Cache Service": {"status": "healthy", "message": "Service is healthy"},
            "Chat Service": {"status": "healthy", "message": "Service is healthy"},
            "VectorStore Service": {"status": "healthy", "message": "Service is healthy"},
            "User Service": {"status": "healthy", "message": "Service is healthy"}
        }
        
        mock_rag_service.verify_services = AsyncMock(return_value=health_status)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 4
        assert all(item["status"] == "healthy" for item in response.json())
    
    def test_health_check_unhealthy(self, client, mock_rag_service):
        """Test health check when some services are unhealthy."""
        health_status = {
            "Cache Service": {"status": "healthy", "message": "Service is healthy"},
            "Chat Service": {"status": "unhealthy", "message": "Service is not responding"},
            "VectorStore Service": {"status": "healthy", "message": "Service is healthy"},
            "User Service": {"status": "healthy", "message": "Service is healthy"}
        }
        
        mock_rag_service.verify_services = AsyncMock(return_value=health_status)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        # Should still return all services, including unhealthy ones
        assert len(response.json()) == 4
    
    def test_health_check_service_not_initialized(self, client):
        """Test health check when service is not initialized."""
        with patch('RAG.rag_api.rag', None):
            response = client.get("/health")
        
        assert response.status_code == 503
    
    def test_health_check_service_error(self, client, mock_rag_service):
        """Test health check when service raises error."""
        mock_rag_service.verify_services = AsyncMock(side_effect=Exception("Health check error"))
        
        response = client.get("/health")
        
        assert response.status_code == 500


class TestRAGAPIRoot:
    """Tests for GET / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["service"] == "RAG Service API"
        assert response.json()["status"] == "running"
        assert "endpoints" in response.json()


class TestRAGAPIAuthentication:
    """Tests for authentication scenarios."""
    
    def test_protected_endpoints_require_auth(self, mock_rag_service):
        """Test that protected endpoints require authentication."""
        from fastapi.testclient import TestClient
        from RAG.rag_api import app
        from RAG.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('RAG.rag_api.rag', mock_rag_service):
            client = TestClient(app)
            
            # Test all protected endpoints require auth
            endpoints = [
                ("GET", "/rag/test/get-session-messages", None),
                ("POST", "/rag/test_session/chat", {"message_id": "test", "role": "user", "content": "Hello"}),
                ("GET", "/rag/get-sessions", None),
                ("POST", "/rag/create-session", None),
                ("DELETE", "/rag/test_session/delete-session", None),
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
    
    def test_public_endpoints_no_auth_required(self, client, mock_rag_service):
        """Test that public endpoints don't require authentication."""
        mock_rag_service.verify_services = AsyncMock(return_value={
            "Cache Service": {"status": "healthy", "message": "Service is healthy"}
        })
        
        # Test health check endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
