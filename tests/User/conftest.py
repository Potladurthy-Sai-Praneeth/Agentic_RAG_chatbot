"""
Pytest configuration and fixtures for UserService tests.
"""
import pytest
import asyncio
import asyncpg
from unittest.mock import AsyncMock, MagicMock, patch
import os
import tempfile
import yaml
from pathlib import Path
from User.user_service import UserService


def create_async_context_manager(mock_obj):
    """Create an async context manager from a mock object."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_obj)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_config_file():
    """Create a temporary config.yaml file for testing."""
    config_data = {
        'postgres': {
            'host': 'localhost',
            'port': 5432,
            'min_connections': 1,
            'max_connections': 20,
            'hex_token_length': 32
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool."""
    pool = AsyncMock(spec=asyncpg.Pool)
    return pool


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = MagicMock()  # Use MagicMock instead of AsyncMock with spec to allow setting magic methods
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchval = AsyncMock()
    return conn


@pytest.fixture
def user_service(temp_config_file, monkeypatch):
    """Create a UserService instance with mocked environment variables."""
    # Mock environment variables
    monkeypatch.setenv('POSTGRES_DB', 'test_db')
    monkeypatch.setenv('POSTGRES_USERNAME', 'test_user')
    monkeypatch.setenv('POSTGRES_PASSWORD', 'test_password')
    
    service = UserService(config_path=temp_config_file)
    return service


@pytest.fixture
def initialized_user_service(user_service, mock_db_pool, mock_connection):
    """Create a UserService instance with initialized pool."""
    async def _init():
        user_service.pool = mock_db_pool
        user_service._initialized = True
        
        # Setup mock pool to return connection
        mock_db_pool.acquire = AsyncMock(return_value=mock_connection)
        mock_db_pool.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.__aexit__ = AsyncMock(return_value=None)
        
        return user_service
    
    return _init


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'user_id': 'test_user_id_12345',
        'user_email': 'test@example.com',
        'username': 'testuser',
        'password': 'TestPassword123!',
        'password_hash': 'hashed_password_here',
        'salt': 'salt_here'
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        'session_id': 'test_session_id_12345',
        'user_id': 'test_user_id_12345',
        'created_at': '2024-01-01 12:00:00'
    }

