"""
Comprehensive tests for RedisService class.
Tests all methods, edge cases, and error scenarios.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import json
import redis
from Cache.cache_service import RedisService
from tests.Cache.conftest import *


class TestRedisServiceInitialization:
    """Tests for RedisService initialization."""
    
    def test_init_with_default_config(self, temp_config_file, mock_redis_client, mock_connection_pool):
        """Test initialization with default config path."""
        with patch('Cache.cache_service.ConnectionPool') as mock_pool_class, \
             patch('Cache.cache_service.redis.Redis') as mock_redis_class:
            
            mock_pool_class.return_value = mock_connection_pool
            mock_redis_class.return_value = mock_redis_client
            mock_redis_client.ping.return_value = True
            
            service = RedisService()
            
            assert service.config is not None
            assert 'redis' in service.config
            assert service.pool == mock_connection_pool
            assert service.client == mock_redis_client
            assert service._initialized is True
    
    def test_init_health_check_fails(self, temp_config_file, mock_redis_client, mock_connection_pool):
        """Test initialization when health check fails."""
        with patch('Cache.cache_service.ConnectionPool') as mock_pool_class, \
             patch('Cache.cache_service.redis.Redis') as mock_redis_class:
            
            mock_pool_class.return_value = mock_connection_pool
            mock_redis_class.return_value = mock_redis_client
            # Mock ping to raise an exception or return False
            mock_redis_client.ping = MagicMock(side_effect=redis.exceptions.ConnectionError("Connection failed"))
            
            with pytest.raises(ConnectionError, match="Unable to connect to Redis server"):
                RedisService()
    
    def test_init_connection_error(self, temp_config_file):
        """Test initialization when connection fails."""
        with patch('Cache.cache_service.ConnectionPool') as mock_pool_class:
            mock_pool_class.side_effect = redis.exceptions.ConnectionError("Connection failed")
            
            with pytest.raises(redis.exceptions.ConnectionError):
                RedisService()


class TestRedisServiceAddMessage:
    """Tests for the add_message() method."""
    
    def test_add_message_success(self, initialized_cache_service, sample_message_data, sample_session_data):
        """Test successful message addition."""
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(return_value=1)
        
        result = initialized_cache_service.add_message(
            sample_session_data['session_id'],
            sample_message_data
        )
        
        assert result is False  # Not at limit yet
        assert initialized_cache_service.client.rpush.called
        assert initialized_cache_service.client.llen.called
    
    def test_add_message_reaches_limit(self, initialized_cache_service, sample_message_data, sample_session_data):
        """Test message addition when limit is reached."""
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(return_value=10)  # At limit
        
        result = initialized_cache_service.add_message(
            sample_session_data['session_id'],
            sample_message_data
        )
        
        assert result is True  # Summarization needed
        assert initialized_cache_service.client.rpush.called
    
    def test_add_message_exceeds_limit(self, initialized_cache_service, sample_message_data, sample_session_data):
        """Test message addition when limit is exceeded."""
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(return_value=11)  # Exceeds limit
        
        result = initialized_cache_service.add_message(
            sample_session_data['session_id'],
            sample_message_data
        )
        
        assert result is True  # Summarization needed
        assert initialized_cache_service.client.rpush.called
    
    def test_add_message_without_initialization_raises_error(self, cache_service, sample_message_data, sample_session_data):
        """Test that add_message() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.add_message(
                sample_session_data['session_id'],
                sample_message_data
            )
    
    def test_add_message_handles_redis_error(self, initialized_cache_service, sample_message_data, sample_session_data):
        """Test that add_message() properly handles Redis errors."""
        initialized_cache_service.client.rpush = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.add_message(
                sample_session_data['session_id'],
                sample_message_data
            )
    
    def test_add_message_handles_general_exception(self, initialized_cache_service, sample_message_data, sample_session_data):
        """Test that add_message() properly handles general exceptions."""
        initialized_cache_service.client.rpush = MagicMock(side_effect=Exception("Unexpected error"))
        
        with pytest.raises(Exception, match="Unexpected error"):
            initialized_cache_service.add_message(
                sample_session_data['session_id'],
                sample_message_data
            )
    
    def test_add_message_json_serialization(self, initialized_cache_service, sample_session_data):
        """Test that message is properly JSON serialized."""
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(return_value=1)
        
        message = {'role': 'user', 'content': 'Test message'}
        initialized_cache_service.add_message(
            sample_session_data['session_id'],
            message
        )
        
        # Verify rpush was called with JSON string
        call_args = initialized_cache_service.client.rpush.call_args
        assert len(call_args[0]) == 2  # key and value
        json_data = json.loads(call_args[0][1])
        assert json_data['role'] == 'user'
        assert json_data['content'] == 'Test message'


class TestRedisServiceGetMessages:
    """Tests for the get_messages() method."""
    
    def test_get_messages_success(self, initialized_cache_service, sample_session_data):
        """Test successful message retrieval."""
        mock_messages = [
            json.dumps({'role': 'user', 'content': 'Hello'}),
            json.dumps({'role': 'assistant', 'content': 'Hi there'})
        ]
        initialized_cache_service.client.lrange = MagicMock(return_value=mock_messages)
        
        messages = initialized_cache_service.get_messages(sample_session_data['session_id'])
        
        assert messages is not None
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[0]['content'] == 'Hello'
        assert messages[1]['role'] == 'assistant'
        assert messages[1]['content'] == 'Hi there'
    
    def test_get_messages_with_limit(self, initialized_cache_service, sample_session_data):
        """Test message retrieval with limit."""
        mock_messages = [
            json.dumps({'role': 'user', 'content': 'Hello'})
        ]
        initialized_cache_service.client.lrange = MagicMock(return_value=mock_messages)
        
        messages = initialized_cache_service.get_messages(
            sample_session_data['session_id'],
            limit=1
        )
        
        assert len(messages) == 1
        # Verify lrange was called with correct indices for limit
        call_args = initialized_cache_service.client.lrange.call_args
        assert call_args[0][1] == -1  # -limit
        assert call_args[0][2] == -1  # -1
    
    def test_get_messages_without_limit(self, initialized_cache_service, sample_session_data):
        """Test message retrieval without limit."""
        mock_messages = [
            json.dumps({'role': 'user', 'content': 'Hello'})
        ]
        initialized_cache_service.client.lrange = MagicMock(return_value=mock_messages)
        
        messages = initialized_cache_service.get_messages(
            sample_session_data['session_id']
        )
        
        # Verify lrange was called with 0, -1 (all messages)
        call_args = initialized_cache_service.client.lrange.call_args
        assert call_args[0][1] == 0
        assert call_args[0][2] == -1
    
    def test_get_messages_empty_list(self, initialized_cache_service, sample_session_data):
        """Test get_messages() returns empty list when no messages exist."""
        initialized_cache_service.client.lrange = MagicMock(return_value=[])
        
        messages = initialized_cache_service.get_messages(sample_session_data['session_id'])
        
        assert messages == []
    
    def test_get_messages_without_initialization_raises_error(self, cache_service, sample_session_data):
        """Test that get_messages() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.get_messages(sample_session_data['session_id'])
    
    def test_get_messages_handles_redis_error(self, initialized_cache_service, sample_session_data):
        """Test that get_messages() properly handles Redis errors."""
        initialized_cache_service.client.lrange = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.get_messages(sample_session_data['session_id'])
    
    def test_get_messages_handles_json_error(self, initialized_cache_service, sample_session_data):
        """Test that get_messages() handles invalid JSON gracefully."""
        initialized_cache_service.client.lrange = MagicMock(return_value=['invalid json'])
        
        with pytest.raises(Exception):  # JSON decode error
            initialized_cache_service.get_messages(sample_session_data['session_id'])


class TestRedisServiceGetMessageCount:
    """Tests for the get_message_count() method."""
    
    def test_get_message_count_success(self, initialized_cache_service, sample_session_data):
        """Test successful message count retrieval."""
        initialized_cache_service.client.llen = MagicMock(return_value=5)
        
        count = initialized_cache_service.get_message_count(sample_session_data['session_id'])
        
        assert count == 5
        assert initialized_cache_service.client.llen.called
    
    def test_get_message_count_zero(self, initialized_cache_service, sample_session_data):
        """Test get_message_count() when no messages exist."""
        initialized_cache_service.client.llen = MagicMock(return_value=0)
        
        count = initialized_cache_service.get_message_count(sample_session_data['session_id'])
        
        assert count == 0
    
    def test_get_message_count_without_initialization_raises_error(self, cache_service, sample_session_data):
        """Test that get_message_count() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.get_message_count(sample_session_data['session_id'])
    
    def test_get_message_count_handles_redis_error(self, initialized_cache_service, sample_session_data):
        """Test that get_message_count() properly handles Redis errors."""
        initialized_cache_service.client.llen = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.get_message_count(sample_session_data['session_id'])


class TestRedisServiceTrimCache:
    """Tests for the trim_cache() method."""
    
    def test_trim_cache_success(self, initialized_cache_service, sample_session_data):
        """Test successful cache trimming."""
        initialized_cache_service.client.llen = MagicMock(return_value=15)  # More than keep_last
        initialized_cache_service.client.ltrim = MagicMock(return_value=True)
        
        result = initialized_cache_service.trim_cache(
            sample_session_data['session_id'],
            keep_last=10
        )
        
        assert result is True
        assert initialized_cache_service.client.ltrim.called
    
    def test_trim_cache_no_trim_needed(self, initialized_cache_service, sample_session_data):
        """Test trim_cache() when trimming is not needed."""
        initialized_cache_service.client.llen = MagicMock(return_value=5)  # Less than keep_last
        
        result = initialized_cache_service.trim_cache(
            sample_session_data['session_id'],
            keep_last=10
        )
        
        assert result is False
        assert not initialized_cache_service.client.ltrim.called
    
    def test_trim_cache_with_none_keep_last(self, initialized_cache_service, sample_session_data):
        """Test trim_cache() with None keep_last."""
        result = initialized_cache_service.trim_cache(
            sample_session_data['session_id'],
            keep_last=None
        )
        
        assert result is False
    
    def test_trim_cache_without_initialization_raises_error(self, cache_service, sample_session_data):
        """Test that trim_cache() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.trim_cache(sample_session_data['session_id'], keep_last=10)
    
    def test_trim_cache_handles_redis_error(self, initialized_cache_service, sample_session_data):
        """Test that trim_cache() properly handles Redis errors."""
        initialized_cache_service.client.llen = MagicMock(return_value=15)
        initialized_cache_service.client.ltrim = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.trim_cache(sample_session_data['session_id'], keep_last=10)


class TestRedisServiceUpdateSummary:
    """Tests for the update_summary() method."""
    
    def test_update_summary_success(self, initialized_cache_service, sample_summary_data):
        """Test successful summary update."""
        initialized_cache_service.client.set = MagicMock(return_value=True)
        
        result = initialized_cache_service.update_summary(
            sample_summary_data['session_id'],
            sample_summary_data['summary']
        )
        
        assert result is True
        assert initialized_cache_service.client.set.called
    
    def test_update_summary_without_initialization_raises_error(self, cache_service, sample_summary_data):
        """Test that update_summary() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.update_summary(
                sample_summary_data['session_id'],
                sample_summary_data['summary']
            )
    
    def test_update_summary_handles_redis_error(self, initialized_cache_service, sample_summary_data):
        """Test that update_summary() properly handles Redis errors."""
        initialized_cache_service.client.set = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.update_summary(
                sample_summary_data['session_id'],
                sample_summary_data['summary']
            )


class TestRedisServiceGetSummary:
    """Tests for the get_summary() method."""
    
    def test_get_summary_success(self, initialized_cache_service, sample_summary_data):
        """Test successful summary retrieval."""
        initialized_cache_service.client.get = MagicMock(return_value=sample_summary_data['summary'])
        
        summary = initialized_cache_service.get_summary(sample_summary_data['session_id'])
        
        assert summary == sample_summary_data['summary']
        assert initialized_cache_service.client.get.called
    
    def test_get_summary_not_found(self, initialized_cache_service, sample_session_data):
        """Test get_summary() when summary doesn't exist."""
        initialized_cache_service.client.get = MagicMock(return_value=None)
        
        summary = initialized_cache_service.get_summary(sample_session_data['session_id'])
        
        assert summary is None
    
    def test_get_summary_without_initialization_raises_error(self, cache_service, sample_session_data):
        """Test that get_summary() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.get_summary(sample_session_data['session_id'])
    
    def test_get_summary_handles_redis_error(self, initialized_cache_service, sample_session_data):
        """Test that get_summary() properly handles Redis errors."""
        initialized_cache_service.client.get = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.get_summary(sample_session_data['session_id'])


class TestRedisServiceClearSession:
    """Tests for the clear_session() method."""
    
    def test_clear_session_success(self, initialized_cache_service, sample_session_data):
        """Test successful session clearing."""
        initialized_cache_service.client.delete = MagicMock(return_value=1)
        
        result = initialized_cache_service.clear_session(sample_session_data['session_id'])
        
        assert result is True
        # Should be called twice (once for messages, once for summary)
        assert initialized_cache_service.client.delete.call_count == 2
    
    def test_clear_session_without_initialization_raises_error(self, cache_service, sample_session_data):
        """Test that clear_session() raises error when not initialized."""
        cache_service._initialized = False
        
        with pytest.raises(RuntimeError, match="RedisService is not initialized"):
            cache_service.clear_session(sample_session_data['session_id'])
    
    def test_clear_session_handles_redis_error(self, initialized_cache_service, sample_session_data):
        """Test that clear_session() properly handles Redis errors."""
        initialized_cache_service.client.delete = MagicMock(side_effect=redis.exceptions.RedisError("Redis error"))
        
        with pytest.raises(redis.exceptions.RedisError, match="Redis error"):
            initialized_cache_service.clear_session(sample_session_data['session_id'])


class TestRedisServiceHealthCheck:
    """Tests for the health_check() method."""
    
    def test_health_check_success(self, initialized_cache_service):
        """Test successful health check."""
        initialized_cache_service.client.ping = MagicMock(return_value=True)
        
        result = initialized_cache_service.health_check()
        
        assert result is True
        assert initialized_cache_service.client.ping.called
    
    def test_health_check_failure(self, initialized_cache_service):
        """Test health check when Redis is unavailable."""
        initialized_cache_service.client.ping = MagicMock(side_effect=redis.exceptions.ConnectionError("Connection failed"))
        
        result = initialized_cache_service.health_check()
        
        assert result is False
    
    def test_health_check_handles_exception(self, initialized_cache_service):
        """Test health check handles exceptions gracefully."""
        initialized_cache_service.client.ping = MagicMock(side_effect=Exception("Unexpected error"))
        
        result = initialized_cache_service.health_check()
        
        assert result is False


class TestRedisServiceClose:
    """Tests for the close() method."""
    
    def test_close_success(self, initialized_cache_service):
        """Test successful close."""
        initialized_cache_service.close()
        
        assert initialized_cache_service._initialized is False
        assert initialized_cache_service.client.close.called
        assert initialized_cache_service.pool.disconnect.called
    
    def test_close_without_client(self, cache_service):
        """Test close() when client is None."""
        cache_service.client = None
        cache_service.pool = MagicMock()
        cache_service._initialized = True
        
        cache_service.close()
        
        assert cache_service._initialized is False
    
    def test_close_without_pool(self, cache_service):
        """Test close() when pool is None."""
        cache_service.client = MagicMock()
        cache_service.pool = None
        cache_service._initialized = True
        
        cache_service.close()
        
        assert cache_service._initialized is False
    
    def test_close_handles_exceptions(self, initialized_cache_service):
        """Test close() handles exceptions gracefully."""
        initialized_cache_service.client.close = MagicMock(side_effect=Exception("Close error"))
        initialized_cache_service.pool.disconnect = MagicMock(side_effect=Exception("Disconnect error"))
        
        # Should not raise exception
        initialized_cache_service.close()
        
        assert initialized_cache_service._initialized is False


class TestRedisServiceContextManager:
    """Tests for context manager functionality."""
    
    def test_context_manager_enters_and_exits(self, cache_service):
        """Test that context manager properly enters and exits."""
        cache_service._initialized = True
        cache_service.close = MagicMock()
        
        with cache_service as service:
            assert service == cache_service
        
        assert cache_service.close.called


class TestRedisServiceEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_add_message_empty_content(self, initialized_cache_service, sample_session_data):
        """Test add_message() with empty content."""
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(return_value=1)
        
        message = {'role': 'user', 'content': ''}
        result = initialized_cache_service.add_message(
            sample_session_data['session_id'],
            message
        )
        
        assert result is False
    
    def test_get_messages_nonexistent_session(self, initialized_cache_service):
        """Test get_messages() for non-existent session."""
        initialized_cache_service.client.lrange = MagicMock(return_value=[])
        
        messages = initialized_cache_service.get_messages("nonexistent_session_id")
        
        assert messages == []
    
    def test_get_message_count_nonexistent_session(self, initialized_cache_service):
        """Test get_message_count() for non-existent session."""
        initialized_cache_service.client.llen = MagicMock(return_value=0)
        
        count = initialized_cache_service.get_message_count("nonexistent_session_id")
        
        assert count == 0
    
    def test_key_generation(self, initialized_cache_service, sample_session_data):
        """Test that keys are generated correctly."""
        messages_key = initialized_cache_service._get_messages_key(sample_session_data['session_id'])
        summary_key = initialized_cache_service._get_summary_key(sample_session_data['session_id'])
        
        assert messages_key == f"session:{sample_session_data['session_id']}:messages"
        assert summary_key == f"session:{sample_session_data['session_id']}:summary"
    
    def test_multiple_sessions_independent(self, initialized_cache_service):
        """Test that multiple sessions are handled independently."""
        session1 = "session1"
        session2 = "session2"
        
        initialized_cache_service.client.rpush = MagicMock(return_value=1)
        initialized_cache_service.client.llen = MagicMock(side_effect=[1, 1])  # Different counts per session
        
        message1 = {'role': 'user', 'content': 'Message 1'}
        message2 = {'role': 'user', 'content': 'Message 2'}
        
        initialized_cache_service.add_message(session1, message1)
        initialized_cache_service.add_message(session2, message2)
        
        # Verify rpush was called twice with different keys
        assert initialized_cache_service.client.rpush.call_count == 2
        call1_key = initialized_cache_service.client.rpush.call_args_list[0][0][0]
        call2_key = initialized_cache_service.client.rpush.call_args_list[1][0][0]
        assert call1_key != call2_key

