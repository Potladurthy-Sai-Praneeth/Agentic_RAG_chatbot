"""
Comprehensive tests for ChatService class.
Tests all methods, edge cases, and error scenarios.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
import asyncio
from cassandra.util import uuid_from_time
from cassandra.cluster import ResultSet
from Chat.chat_service import ChatService
import os
from tests.Chat.conftest import create_async_context_manager


class TestChatServiceInitialization:
    """Tests for ChatService initialization."""
    
    def test_init_with_default_config(self, temp_config_file, monkeypatch):
        """Test initialization with default config path."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        service = ChatService(config_path=temp_config_file)
        
        assert service.config is not None
        assert 'cassandra' in service.config
        assert service.cluster is None
        assert service.session is None
        assert service._initialized is False
        assert isinstance(service.prepared_statements, dict)
    
    def test_init_with_custom_config_path(self, temp_config_file, monkeypatch):
        """Test initialization with custom config path."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        service = ChatService(config_path=temp_config_file)
        assert service.config is not None
        assert 'cassandra' in service.config


class TestChatServiceInitialize:
    """Tests for the initialize() method."""
    
    @pytest.mark.asyncio
    async def test_initialize_creates_cluster_and_schema(self, chat_service, mock_cluster, mock_session, monkeypatch):
        """Test that initialize() creates cluster and initializes schema."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        with patch('Chat.chat_service.Cluster') as mock_cluster_class:
            mock_cluster_instance = MagicMock()
            mock_cluster_instance.connect = MagicMock(return_value=mock_session)
            mock_cluster_class.return_value = mock_cluster_instance
            
            # Mock the executor run_in_executor
            async def mock_run_in_executor(executor, func, *args):
                return func(*args)
            
            chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
            mock_session.execute = MagicMock()
            mock_session.prepare = MagicMock(return_value=MagicMock())
            
            await chat_service.initialize()
            
            assert chat_service.cluster == mock_cluster_instance
            assert chat_service.session == mock_session
            assert chat_service._initialized is True
            assert mock_cluster_class.called
            # Verify schema creation was called
            assert mock_session.execute.called
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, chat_service, mock_cluster, mock_session, monkeypatch):
        """Test that initialize() is idempotent."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        with patch('Chat.chat_service.Cluster') as mock_cluster_class:
            mock_cluster_instance = MagicMock()
            mock_cluster_instance.connect = MagicMock(return_value=mock_session)
            mock_cluster_class.return_value = mock_cluster_instance
            
            async def mock_run_in_executor(executor, func, *args):
                return func(*args)
            
            chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
            mock_session.execute = MagicMock()
            mock_session.prepare = MagicMock(return_value=MagicMock())
            
            await chat_service.initialize()
            first_call_count = mock_cluster_class.call_count
            
            await chat_service.initialize()
            # Should not create cluster again
            assert mock_cluster_class.call_count == first_call_count
    
    @pytest.mark.asyncio
    async def test_initialize_handles_errors(self, chat_service, monkeypatch):
        """Test that initialize() properly handles errors."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        with patch('Chat.chat_service.Cluster') as mock_cluster_class:
            mock_cluster_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                await chat_service.initialize()
            
            assert chat_service._initialized is False


class TestChatServiceStoreMessage:
    """Tests for the store_message() method."""
    
    @pytest.mark.asyncio
    async def test_store_message_success(self, initialized_chat_service, sample_message_data):
        """Test successful message storage."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        result = await initialized_chat_service.store_message(
            sample_message_data['session_id'],
            sample_message_data['user_id'],
            sample_message_data['role'],
            sample_message_data['content']
        )
        
        assert result is not None
        assert 'message_id' in result
        assert 'timestamp' in result
        assert initialized_chat_service.session.execute_async.called
    
    @pytest.mark.asyncio
    async def test_store_message_without_initialization_raises_error(self, chat_service, sample_message_data):
        """Test that store_message() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.store_message(
                sample_message_data['session_id'],
                sample_message_data['user_id'],
                sample_message_data['role'],
                sample_message_data['content']
            )
    
    @pytest.mark.asyncio
    async def test_store_message_handles_exceptions(self, initialized_chat_service, sample_message_data):
        """Test that store_message() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.store_message(
                sample_message_data['session_id'],
                sample_message_data['user_id'],
                sample_message_data['role'],
                sample_message_data['content']
            )


class TestChatServiceGetMessages:
    """Tests for the get_messages() method."""
    
    @pytest.mark.asyncio
    async def test_get_messages_success(self, initialized_chat_service, sample_message_data):
        """Test successful message retrieval."""
        # Mock row objects
        mock_row1 = MagicMock()
        mock_row1.role = 'user'
        mock_row1.content = 'Hello'
        mock_row1.message_id = uuid_from_time(datetime.now())
        mock_row1.timestamp = datetime.now()
        
        mock_row2 = MagicMock()
        mock_row2.role = 'assistant'
        mock_row2.content = 'Hi there'
        mock_row2.message_id = uuid_from_time(datetime.now())
        mock_row2.timestamp = datetime.now()
        
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=[mock_row1, mock_row2])
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        messages = await initialized_chat_service.get_messages(sample_message_data['session_id'])
        
        assert messages is not None
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert 'role' in messages[0]
        assert 'content' in messages[0]
    
    @pytest.mark.asyncio
    async def test_get_messages_with_limit(self, initialized_chat_service, sample_message_data):
        """Test message retrieval with limit."""
        mock_row = MagicMock()
        mock_row.role = 'user'
        mock_row.content = 'Hello'
        mock_row.message_id = uuid_from_time(datetime.now())
        mock_row.timestamp = datetime.now()
        
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=[mock_row])
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        messages = await initialized_chat_service.get_messages(sample_message_data['session_id'], limit=1)
        
        assert len(messages) == 1
    
    @pytest.mark.asyncio
    async def test_get_messages_empty_list(self, initialized_chat_service, sample_message_data):
        """Test get_messages() returns empty list when no messages exist."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=[])
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        messages = await initialized_chat_service.get_messages(sample_message_data['session_id'])
        
        assert messages == []
    
    @pytest.mark.asyncio
    async def test_get_messages_without_initialization_raises_error(self, chat_service, sample_message_data):
        """Test that get_messages() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.get_messages(sample_message_data['session_id'])
    
    @pytest.mark.asyncio
    async def test_get_messages_handles_exceptions(self, initialized_chat_service, sample_message_data):
        """Test that get_messages() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.get_messages(sample_message_data['session_id'])


class TestChatServiceGetSummary:
    """Tests for the get_summary() method."""
    
    @pytest.mark.asyncio
    async def test_get_summary_success(self, initialized_chat_service, sample_summary_data):
        """Test successful summary retrieval."""
        mock_row = MagicMock()
        mock_row.session_id = sample_summary_data['session_id']
        mock_row.user_id = sample_summary_data['user_id']
        mock_row.summary = sample_summary_data['summary']
        mock_row.last_updated = sample_summary_data['last_updated']
        mock_row.message_count = sample_summary_data['message_count']
        
        mock_result_set = MagicMock()
        mock_result_set.one = MagicMock(return_value=mock_row)
        
        async def mock_run_in_executor(executor, func, *args):
            # func() returns the result_set from execute_async().result()
            return mock_result_set
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=MagicMock())
        
        summary = await initialized_chat_service.get_summary(sample_summary_data['session_id'])
        
        assert summary is not None
        assert summary['session_id'] == sample_summary_data['session_id']
        assert summary['summary'] == sample_summary_data['summary']
    
    @pytest.mark.asyncio
    async def test_get_summary_not_found(self, initialized_chat_service, sample_summary_data):
        """Test get_summary() when summary doesn't exist."""
        mock_result_set = MagicMock()
        mock_result_set.one = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            # func() returns the result_set from execute_async().result()
            return mock_result_set
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=MagicMock())
        
        summary = await initialized_chat_service.get_summary(sample_summary_data['session_id'])
        
        assert summary is None
    
    @pytest.mark.asyncio
    async def test_get_summary_without_initialization_raises_error(self, chat_service, sample_summary_data):
        """Test that get_summary() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.get_summary(sample_summary_data['session_id'])
    
    @pytest.mark.asyncio
    async def test_get_summary_handles_exceptions(self, initialized_chat_service, sample_summary_data):
        """Test that get_summary() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.get_summary(sample_summary_data['session_id'])


class TestChatServiceInsertSummary:
    """Tests for the insert_summary() method."""
    
    @pytest.mark.asyncio
    async def test_insert_summary_success(self, initialized_chat_service, sample_summary_data):
        """Test successful summary insertion."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        result = await initialized_chat_service.insert_summary(
            sample_summary_data['session_id'],
            sample_summary_data['user_id'],
            sample_summary_data['summary'],
            sample_summary_data['message_count']
        )
        
        assert result is True
        assert initialized_chat_service.session.execute_async.called
    
    @pytest.mark.asyncio
    async def test_insert_summary_without_initialization_raises_error(self, chat_service, sample_summary_data):
        """Test that insert_summary() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.insert_summary(
                sample_summary_data['session_id'],
                sample_summary_data['user_id'],
                sample_summary_data['summary'],
                sample_summary_data['message_count']
            )
    
    @pytest.mark.asyncio
    async def test_insert_summary_handles_exceptions(self, initialized_chat_service, sample_summary_data):
        """Test that insert_summary() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.insert_summary(
                sample_summary_data['session_id'],
                sample_summary_data['user_id'],
                sample_summary_data['summary'],
                sample_summary_data['message_count']
            )


class TestChatServiceGetMessageCount:
    """Tests for the get_message_count() method."""
    
    @pytest.mark.asyncio
    async def test_get_message_count_success(self, initialized_chat_service, sample_session_data):
        """Test successful message count retrieval."""
        mock_result_set = MagicMock()
        # COUNT(*) returns a row that when indexed [0] gives the count
        mock_result_set.one = MagicMock(return_value=[5])
        
        async def mock_run_in_executor(executor, func, *args):
            # func() returns the result_set from execute_async().result()
            return mock_result_set
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=MagicMock())
        
        count = await initialized_chat_service.get_message_count(sample_session_data['session_id'])
        
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_get_message_count_zero(self, initialized_chat_service, sample_session_data):
        """Test get_message_count() when no messages exist."""
        mock_result_set = MagicMock()
        mock_result_set.one = MagicMock(return_value=[0])
        
        async def mock_run_in_executor(executor, func, *args):
            # func() returns the result_set from execute_async().result()
            return mock_result_set
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=MagicMock())
        
        count = await initialized_chat_service.get_message_count(sample_session_data['session_id'])
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_get_message_count_without_initialization_raises_error(self, chat_service, sample_session_data):
        """Test that get_message_count() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.get_message_count(sample_session_data['session_id'])
    
    @pytest.mark.asyncio
    async def test_get_message_count_handles_exceptions(self, initialized_chat_service, sample_session_data):
        """Test that get_message_count() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.get_message_count(sample_session_data['session_id'])


class TestChatServiceDeleteSession:
    """Tests for the delete_session() method."""
    
    @pytest.mark.asyncio
    async def test_delete_session_success(self, initialized_chat_service, sample_session_data):
        """Test successful session deletion."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        result = await initialized_chat_service.delete_session(sample_session_data['session_id'])
        
        assert result is True
        # Should be called twice (once for messages, once for summary)
        assert initialized_chat_service.session.execute_async.call_count == 2
    
    @pytest.mark.asyncio
    async def test_delete_session_without_initialization_raises_error(self, chat_service, sample_session_data):
        """Test that delete_session() raises error when not initialized."""
        chat_service._initialized = False
        
        with pytest.raises(Exception, match="CassandraManager not initialized"):
            await chat_service.delete_session(sample_session_data['session_id'])
    
    @pytest.mark.asyncio
    async def test_delete_session_handles_exceptions(self, initialized_chat_service, sample_session_data):
        """Test that delete_session() properly handles exceptions."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Database error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        with pytest.raises(Exception, match="Database error"):
            await initialized_chat_service.delete_session(sample_session_data['session_id'])


class TestChatServiceHealthCheck:
    """Tests for the health_check() method."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, initialized_chat_service):
        """Test successful health check."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        result = await initialized_chat_service.health_check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, chat_service):
        """Test health check when service is not initialized."""
        chat_service._initialized = False
        
        result = await chat_service.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_database_error(self, initialized_chat_service):
        """Test health check when database query fails."""
        async def mock_run_in_executor(executor, func, *args):
            raise Exception("Connection error")
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        result = await initialized_chat_service.health_check()
        
        assert result is False


class TestChatServiceClose:
    """Tests for the close() method."""
    
    @pytest.mark.asyncio
    async def test_close_success(self, initialized_chat_service, mock_cluster):
        """Test successful close."""
        initialized_chat_service.cluster = mock_cluster
        mock_cluster.shutdown = MagicMock()
        
        async def mock_run_in_executor(executor, func, *args):
            return func(*args)
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        
        await initialized_chat_service.close()
        
        assert initialized_chat_service._initialized is False
        assert mock_cluster.shutdown.called
    
    @pytest.mark.asyncio
    async def test_close_without_cluster(self, chat_service):
        """Test close() when cluster is None."""
        chat_service.cluster = None
        chat_service._initialized = True
        
        # Should not raise an error
        await chat_service.close()
        
        assert chat_service._initialized is False


class TestChatServiceContextManager:
    """Tests for async context manager functionality."""
    
    @pytest.mark.asyncio
    async def test_context_manager_initializes_and_closes(self, chat_service, mock_cluster, mock_session, monkeypatch):
        """Test that context manager properly initializes and closes."""
        monkeypatch.setenv('CASSANDRA_KEYSPACE_NAME', 'test_keyspace')
        monkeypatch.setenv('CASSANDRA_CHAT_TABLE_NAME', 'test_chat')
        monkeypatch.setenv('CASSANDRA_SUMMARY_TABLE_NAME', 'test_summary')
        
        with patch('Chat.chat_service.Cluster') as mock_cluster_class:
            mock_cluster_instance = MagicMock()
            mock_cluster_instance.connect = MagicMock(return_value=mock_session)
            mock_cluster_instance.shutdown = MagicMock()
            mock_cluster_class.return_value = mock_cluster_instance
            
            async def mock_run_in_executor(executor, func, *args):
                return func(*args)
            
            chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
            mock_session.execute = MagicMock()
            mock_session.prepare = MagicMock(return_value=MagicMock())
            
            async with chat_service as service:
                assert service._initialized is True
            
            # Verify close was called
            assert mock_cluster_instance.shutdown.called


class TestChatServiceEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_store_message_empty_strings(self, initialized_chat_service):
        """Test store_message() with empty strings."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=None)
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        # Should not raise error, but may log warnings
        result = await initialized_chat_service.store_message("", "", "", "")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_messages_nonexistent_session(self, initialized_chat_service):
        """Test get_messages() for non-existent session."""
        mock_result_set = MagicMock()
        mock_result_set.result = MagicMock(return_value=[])
        
        async def mock_run_in_executor(executor, func, *args):
            return func()
        
        initialized_chat_service.loop.run_in_executor = AsyncMock(side_effect=mock_run_in_executor)
        initialized_chat_service.session.execute_async = MagicMock(return_value=mock_result_set)
        
        messages = await initialized_chat_service.get_messages("nonexistent_session_id")
        
        assert messages == []

