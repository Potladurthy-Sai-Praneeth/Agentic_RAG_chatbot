"""
Pytest configuration and fixtures for CacheService tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import os
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
import redis
from Cache.cache_service import RedisService


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
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': True,
            'max_connections': 10
        },
        'cache': {
            'message_limit': 10
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
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock(spec=redis.Redis)
    client.ping = MagicMock(return_value=True)
    client.rpush = MagicMock(return_value=1)
    client.lrange = MagicMock(return_value=[])
    client.llen = MagicMock(return_value=0)
    client.ltrim = MagicMock(return_value=True)
    client.set = MagicMock(return_value=True)
    client.get = MagicMock(return_value=None)
    client.delete = MagicMock(return_value=1)
    client.close = MagicMock()
    return client


@pytest.fixture
def mock_connection_pool():
    """Create a mock Redis connection pool."""
    pool = MagicMock(spec=redis.connection.ConnectionPool)
    pool.disconnect = MagicMock()
    return pool


@pytest.fixture
def cache_service(temp_config_file, mock_redis_client, mock_connection_pool):
    """Create a RedisService instance with mocked Redis client."""
    with patch('Cache.cache_service.ConnectionPool') as mock_pool_class, \
         patch('Cache.cache_service.redis.Redis') as mock_redis_class:
        
        mock_pool_class.return_value = mock_connection_pool
        mock_redis_class.return_value = mock_redis_client
        
        # Mock the health check to pass
        mock_redis_client.ping.return_value = True
        
        # Create service instance without calling __init__
        service = RedisService.__new__(RedisService)
        service.config = {
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'decode_responses': True,
                'max_connections': 10
            },
            'cache': {
                'message_limit': 10
            }
        }
        service.pool = mock_connection_pool
        service.client = mock_redis_client
        service._initialized = True
        
        return service


@pytest.fixture
def initialized_cache_service(cache_service):
    """Create a RedisService instance that is initialized."""
    return cache_service


@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        'role': 'user',
        'content': 'Hello, this is a test message',
        'timestamp': datetime.now()
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        'session_id': 'test_session_12345',
        'user_id': 'test_user_12345'
    }


@pytest.fixture
def sample_summary_data():
    """Sample summary data for testing."""
    return {
        'session_id': 'test_session_12345',
        'summary': 'This is a test summary'
    }

