"""
Pytest configuration and fixtures for ChatService tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import os
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from cassandra.cluster import Session, ResultSet
from cassandra.util import uuid_from_time
from Chat.chat_service import ChatService


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
        'cassandra': {
            'host': 'localhost',
            'port': 9042,
            'replication_factor': 1,
            'max_workers': 5
        },
        'jwt': {
            'access_token_expires': 30,
            'refresh_token_expires': 7,
            'algorithm': 'HS256'
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
def mock_cluster():
    """Create a mock Cassandra cluster."""
    cluster = MagicMock()
    return cluster


@pytest.fixture
def mock_session():
    """Create a mock Cassandra session."""
    session = MagicMock(spec=Session)
    session.execute = MagicMock()
    session.execute_async = MagicMock()
    session.prepare = MagicMock()
    session.set_keyspace = MagicMock()
    return session


@pytest.fixture
def mock_result_set():
    """Create a mock Cassandra ResultSet."""
    result_set = MagicMock(spec=ResultSet)
    result_set.result = MagicMock()
    return result_set


@pytest.fixture
def chat_service(temp_config_file, monkeypatch):
    """Create a ChatService instance with mocked environment variables."""
    # Mock environment variables
    monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
    monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat_messages')
    monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_session_summaries')
    
    service = ChatService(config_path=temp_config_file)
    return service


@pytest.fixture
def initialized_chat_service(chat_service, mock_cluster, mock_session):
    """Create a ChatService instance with initialized cluster and session."""
    chat_service.cluster = mock_cluster
    chat_service.session = mock_session
    chat_service._initialized = True
    
    # Setup mock prepared statements
    chat_service.prepared_statements = {
        'insert_message': MagicMock(),
        'select_messages': MagicMock(),
        'select_messages_limit': MagicMock(),
        'delete_session_messages': MagicMock(),
        'get_chat_message_count': MagicMock(),
        'insert_summary': MagicMock(),
        'select_summary': MagicMock(),
        'delete_summary': MagicMock()
    }
    
    return chat_service


@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        'session_id': 'test_session_12345',
        'user_id': 'test_user_12345',
        'role': 'user',
        'content': 'Hello, this is a test message',
        'message_id': str(uuid_from_time(datetime.now())),
        'timestamp': datetime.now()
    }


@pytest.fixture
def sample_summary_data():
    """Sample summary data for testing."""
    return {
        'session_id': 'test_session_12345',
        'user_id': 'test_user_12345',
        'summary': 'This is a test summary',
        'message_count': 10,
        'last_updated': datetime.now()
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        'session_id': 'test_session_12345',
        'user_id': 'test_user_12345'
    }

