"""
Pytest configuration and fixtures for RAG Service tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
import tempfile
import yaml
from datetime import datetime
from RAG.rag_service import RAGService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_rag_service():
    """Create a mock RAGService."""
    service = MagicMock(spec=RAGService)
    service._initialized = True
    return service


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {"user_id": "test_user_12345"}


@pytest.fixture
def client(mock_rag_service):
    """Create a test client with mocked RAG service."""
    from fastapi.testclient import TestClient
    from RAG.rag_api import app
    from RAG.jwt_utils import get_current_user, verify_token
    
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
    
    # Patch verify_token in the middleware and the global rag
    with patch('RAG.rag_api.rag', mock_rag_service), \
         patch('RAG.rag_api.verify_token', mock_verify_token):
        yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        'session_id': 'test_session_12345',
        'user_id': 'test_user_12345',
        'created_at': datetime.now()
    }


@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        'message_id': 'test_message_12345',
        'role': 'user',
        'content': 'Hello, how are you?',
        'timestamp': datetime.now()
    }


@pytest.fixture
def sample_chat_messages():
    """Sample chat messages for testing."""
    return [
        {
            'message_id': 'msg1',
            'role': 'user',
            'content': 'Hello',
            'timestamp': datetime.now()
        },
        {
            'message_id': 'msg2',
            'role': 'assistant',
            'content': 'Hi there!',
            'timestamp': datetime.now()
        }
    ]


@pytest.fixture
def sample_sessions():
    """Sample sessions for testing."""
    return [
        {
            'session_id': 'session1',
            'created_at': datetime.now(),
            'title': 'Session 1'
        },
        {
            'session_id': 'session2',
            'created_at': datetime.now(),
            'title': None
        }
    ]
