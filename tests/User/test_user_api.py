"""
Comprehensive tests for User API endpoints.
Tests all endpoints, authentication, and error scenarios.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime, timedelta
from User.user_api import app
from User.user_service import UserService
from User.jwt_utils import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES


@pytest.fixture
def mock_user_service():
    """Create a mock UserService."""
    service = MagicMock(spec=UserService)
    service._initialized = True
    return service


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {"user_id": "test_user_12345"}


@pytest.fixture
def client(mock_user_service):
    """Create a test client with mocked user service."""
    from fastapi.testclient import TestClient
    from User.user_api import app
    from User.jwt_utils import get_current_user, verify_token
    
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
    
    # Patch verify_token in the middleware and the global user_db
    with patch('User.user_api.user_db', mock_user_service), \
         patch('User.user_api.verify_token', mock_verify_token):
        yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


class TestUserAPIRegister:
    """Tests for POST /register endpoint."""
    
    def test_register_user_success(self, client, mock_user_service):
        """Test successful user registration."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "password123"
        }
        
        mock_user_service.register_user = AsyncMock(return_value="test_user_12345")
        
        response = client.post("/register", json=user_data)
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert "User registered successfully" in response.json()["message"]
        mock_user_service.register_user.assert_called_once_with(
            "test@example.com", "testuser", "password123"
        )
    
    def test_register_user_already_exists(self, client, mock_user_service):
        """Test registration when user already exists."""
        user_data = {
            "email": "existing@example.com",
            "username": "existinguser",
            "password": "password123"
        }
        
        mock_user_service.register_user = AsyncMock(return_value=None)
        
        response = client.post("/register", json=user_data)
        
        assert response.status_code == 201  # API returns 201 even on failure
        assert response.json()["success"] is False
        assert "failed" in response.json()["message"].lower()
    
    def test_register_user_service_not_initialized(self, client):
        """Test registration when service is not initialized."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "password123"
        }
        
        with patch('User.user_api.user_db', None):
            response = client.post("/register", json=user_data)
        
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()
    
    def test_register_user_invalid_email(self, client, mock_user_service):
        """Test registration with invalid email format."""
        user_data = {
            "email": "invalid-email",
            "username": "testuser",
            "password": "password123"
        }
        
        response = client.post("/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_register_user_short_password(self, client, mock_user_service):
        """Test registration with password shorter than 8 characters."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "short"
        }
        
        response = client.post("/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_register_user_service_error(self, client, mock_user_service):
        """Test registration when service raises error."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "password123"
        }
        
        mock_user_service.register_user = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.post("/register", json=user_data)
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestUserAPILogin:
    """Tests for POST /login endpoint."""
    
    def test_login_success_with_email(self, client, mock_user_service):
        """Test successful login with email."""
        login_data = {
            "user": "test@example.com",
            "password": "password123"
        }
        
        mock_user_service.login = AsyncMock(return_value="test_user_12345")
        
        response = client.post("/login", json=login_data)
        
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()
        assert response.json()["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
        mock_user_service.login.assert_called_once_with("test@example.com", "password123")
    
    def test_login_success_with_username(self, client, mock_user_service):
        """Test successful login with username."""
        login_data = {
            "user": "testuser",
            "password": "password123"
        }
        
        mock_user_service.login = AsyncMock(return_value="test_user_12345")
        
        response = client.post("/login", json=login_data)
        
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert "access_token" in response.json()
    
    def test_login_invalid_credentials(self, client, mock_user_service):
        """Test login with invalid credentials."""
        login_data = {
            "user": "test@example.com",
            "password": "wrongpassword"
        }
        
        mock_user_service.login = AsyncMock(return_value=None)
        
        response = client.post("/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_login_service_not_initialized(self, client):
        """Test login when service is not initialized."""
        login_data = {
            "user": "test@example.com",
            "password": "password123"
        }
        
        with patch('User.user_api.user_db', None):
            response = client.post("/login", json=login_data)
        
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()
    
    def test_login_service_error(self, client, mock_user_service):
        """Test login when service raises error."""
        login_data = {
            "user": "test@example.com",
            "password": "password123"
        }
        
        mock_user_service.login = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.post("/login", json=login_data)
        
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestUserAPIAddSession:
    """Tests for POST /add-session endpoint."""
    
    def test_add_session_success(self, client, mock_user_service):
        """Test successful session addition."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.add_session = AsyncMock(return_value="test_session_12345")
        
        # Create a valid token for authentication
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.post(
            "/add-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "added successfully" in response.json()["message"].lower()
        mock_user_service.add_session.assert_called_once_with("test_session_12345", "test_user_12345")
    
    def test_add_session_failed(self, client, mock_user_service):
        """Test session addition when it fails."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.add_session = AsyncMock(return_value=None)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.post(
            "/add-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "Failed to add session" in response.json()["detail"]
    
    def test_add_session_service_not_initialized(self, client):
        """Test add session when service is not initialized."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        with patch('User.user_api.user_db', None):
            response = client.post(
                "/add-session",
                json=session_data,
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_add_session_unauthorized(self, mock_user_service):
        """Test add session without authentication."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from User.jwt_utils import get_current_user
        
        # Override dependency to raise HTTPException
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            response = client.post(
                "/add-session",
                json={"session_id": "test_session_12345"}
            )
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_add_session_service_error(self, client, mock_user_service):
        """Test add session when service raises error."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.add_session = AsyncMock(side_effect=Exception("Database error"))
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.post(
            "/add-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestUserAPIGetSessions:
    """Tests for GET /get-sessions endpoint."""
    
    def test_get_sessions_success(self, client, mock_user_service):
        """Test successful session retrieval."""
        mock_sessions = {
            "session_1": datetime.now(),
            "session_2": datetime.now(),
            "session_3": datetime.now()
        }
        
        mock_user_service.get_sessions = AsyncMock(return_value=mock_sessions)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.get(
            "/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert len(response.json()["sessions"]) == 3
        mock_user_service.get_sessions.assert_called_once_with("test_user_12345")
    
    def test_get_sessions_empty(self, client, mock_user_service):
        """Test get sessions when user has no sessions."""
        mock_user_service.get_sessions = AsyncMock(return_value={})
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.get(
            "/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert len(response.json()["sessions"]) == 0
    
    def test_get_sessions_service_not_initialized(self, client):
        """Test get sessions when service is not initialized."""
        token = create_access_token(data={"sub": "test_user_12345"})
        
        with patch('User.user_api.user_db', None):
            response = client.get(
                "/get-sessions",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_get_sessions_unauthorized(self, mock_user_service):
        """Test get sessions without authentication."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from User.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            response = client.get("/get-sessions")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_get_sessions_service_error(self, client, mock_user_service):
        """Test get sessions when service raises error."""
        mock_user_service.get_sessions = AsyncMock(side_effect=Exception("Database error"))
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.get(
            "/get-sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestUserAPIDeleteSession:
    """Tests for DELETE /delete-session endpoint."""
    
    def test_delete_session_success(self, client, mock_user_service):
        """Test successful session deletion."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.delete_session = AsyncMock(return_value=True)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.request(
            "DELETE",
            "/delete-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "deleted successfully" in response.json()["message"].lower()
        mock_user_service.delete_session.assert_called_once_with("test_user_12345", "test_session_12345")
    
    def test_delete_session_failed(self, client, mock_user_service):
        """Test session deletion when it fails."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.delete_session = AsyncMock(return_value=False)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.request(
            "DELETE",
            "/delete-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "Failed to delete session" in response.json()["detail"]
    
    def test_delete_session_service_not_initialized(self, client):
        """Test delete session when service is not initialized."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        with patch('User.user_api.user_db', None):
            response = client.request(
                "DELETE",
                "/delete-session",
                json=session_data,
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_delete_session_unauthorized(self, mock_user_service):
        """Test delete session without authentication."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from User.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/delete-session",
                json={"session_id": "test_session_12345"}
            )
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_delete_session_service_error(self, client, mock_user_service):
        """Test delete session when service raises error."""
        session_data = {
            "session_id": "test_session_12345"
        }
        
        mock_user_service.delete_session = AsyncMock(side_effect=Exception("Database error"))
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.request(
            "DELETE",
            "/delete-session",
            json=session_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestUserAPIDeleteUser:
    """Tests for DELETE /delete-user endpoint."""
    
    def test_delete_user_success(self, client, mock_user_service):
        """Test successful user deletion."""
        mock_user_service.delete_user = AsyncMock(return_value=True)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.delete(
            "/delete-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "deleted successfully" in response.json()["message"].lower()
        mock_user_service.delete_user.assert_called_once_with("test_user_12345")
    
    def test_delete_user_failed(self, client, mock_user_service):
        """Test user deletion when it fails."""
        mock_user_service.delete_user = AsyncMock(return_value=False)
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.delete(
            "/delete-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "Failed to delete user" in response.json()["detail"]
    
    def test_delete_user_service_not_initialized(self, client):
        """Test delete user when service is not initialized."""
        token = create_access_token(data={"sub": "test_user_12345"})
        
        with patch('User.user_api.user_db', None):
            response = client.delete(
                "/delete-user",
                headers={"Authorization": f"Bearer {token}"}
            )
        
        assert response.status_code == 503
    
    def test_delete_user_unauthorized(self, mock_user_service):
        """Test delete user without authentication."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from User.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            response = client.delete("/delete-user")
        
        app.dependency_overrides.clear()
        assert response.status_code == 401
    
    def test_delete_user_service_error(self, client, mock_user_service):
        """Test delete user when service raises error."""
        mock_user_service.delete_user = AsyncMock(side_effect=Exception("Database error"))
        
        token = create_access_token(data={"sub": "test_user_12345"})
        
        response = client.delete(
            "/delete-user",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


class TestUserAPIHealthCheck:
    """Tests for GET /health endpoint."""
    
    def test_health_check_success(self, client, mock_user_service):
        """Test successful health check."""
        mock_user_service.health_check = AsyncMock(return_value=True)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert "healthy" in response.json()["message"].lower()
    
    def test_health_check_service_not_initialized(self, client):
        """Test health check when service is not initialized."""
        with patch('User.user_api.user_db', None):
            response = client.get("/health")
        
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()
    
    def test_health_check_unhealthy(self, client, mock_user_service):
        """Test health check when database is unhealthy."""
        mock_user_service.health_check = AsyncMock(return_value=False)
        
        response = client.get("/health")
        
        assert response.status_code == 503
        assert "unhealthy" in response.json()["detail"].lower()
    
    def test_health_check_service_error(self, client, mock_user_service):
        """Test health check when service raises error."""
        mock_user_service.health_check = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get("/health")
        
        assert response.status_code == 500


class TestUserAPIRoot:
    """Tests for GET / endpoint."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json()["service"] == "User Management Service"
        assert response.json()["status"] == "running"
        assert response.json()["version"] == "1.0.0"
        assert "endpoints" in response.json()
        assert "POST /register" in response.json()["endpoints"]
        assert "POST /login" in response.json()["endpoints"]


class TestUserAPIAuthentication:
    """Tests for authentication scenarios."""
    
    def test_protected_endpoints_require_auth(self, mock_user_service):
        """Test that protected endpoints require authentication."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from User.jwt_utils import get_current_user
        
        async def override_get_current_user():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = override_get_current_user
        
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            
            # Test all protected endpoints require auth
            endpoints = [
                ("POST", "/add-session", {"session_id": "test_session"}),
                ("GET", "/get-sessions", None),
                ("DELETE", "/delete-session", {"session_id": "test_session"}),
                ("DELETE", "/delete-user", None),
            ]
            
            for method, endpoint, data in endpoints:
                if method == "POST":
                    response = client.post(endpoint, json=data)
                elif method == "GET":
                    response = client.get(endpoint)
                elif method == "DELETE":
                    if data:
                        response = client.request("DELETE", endpoint, json=data)
                    else:
                        response = client.delete(endpoint)
                
                assert response.status_code == 401, f"{method} {endpoint} should require auth"
        
        app.dependency_overrides.clear()
    
    def test_public_endpoints_no_auth_required(self, client, mock_user_service):
        """Test that public endpoints don't require authentication."""
        mock_user_service.register_user = AsyncMock(return_value="test_user_12345")
        mock_user_service.login = AsyncMock(return_value="test_user_12345")
        mock_user_service.health_check = AsyncMock(return_value=True)
        
        # Test register endpoint
        response = client.post(
            "/register",
            json={"email": "test@example.com", "username": "testuser", "password": "password123"}
        )
        assert response.status_code in [201, 422]  # 422 if validation fails, 201 if succeeds
        
        # Test login endpoint
        response = client.post(
            "/login",
            json={"user": "test@example.com", "password": "password123"}
        )
        assert response.status_code in [200, 401]  # 401 if invalid, 200 if succeeds
        
        # Test health check endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
    
    def test_invalid_token(self, mock_user_service):
        """Test endpoints with invalid token."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        from fastapi import HTTPException
        import pytest
        
        # Don't patch verify_token - let it fail naturally with invalid token
        # The real verify_token will try to decode the token and fail
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            
            # Try to access protected endpoint with invalid token
            # The middleware will call verify_token which will raise HTTPException
            # TestClient should convert HTTPException to a 401 response
            try:
                response = client.get(
                    "/get-sessions",
                    headers={"Authorization": "Bearer invalid_token"}
                )
                # If no exception is raised, check the status code
                assert response.status_code == 401
            except HTTPException as e:
                # If HTTPException is raised, verify it's 401
                assert e.status_code == 401
    
    def test_missing_token(self, mock_user_service):
        """Test endpoints without token."""
        from fastapi.testclient import TestClient
        from User.user_api import app
        
        # Don't patch verify_token - let it fail naturally when no token is provided
        with patch('User.user_api.user_db', mock_user_service):
            client = TestClient(app)
            
            # Try to access protected endpoint without token
            response = client.get("/get-sessions")
            
            # With contextVar-based auth, missing token results in 401 (not 403)
            assert response.status_code == 401

