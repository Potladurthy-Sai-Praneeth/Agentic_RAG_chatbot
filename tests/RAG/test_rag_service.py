"""
Comprehensive tests for RAGService class.
Tests all methods, edge cases, and error scenarios.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
import uuid
from RAG.rag_service import RAGService
from RAG.client import ServiceClient


class TestRAGServiceInitialization:
    """Tests for RAGService initialization."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return {
            'models': {
                'summary': {'provider': 'gemini', 'name': 'gemini-2.5-flash'},
                'chat': {'provider': 'gemini', 'name': 'gemini-2.5-pro'}
            },
            'prompts': {
                'system_template': 'You are {chatbot_name}',
                'summary_template': 'Summarize: {current_summary} {conversation}'
            },
            'user': {'name': 'Test User', 'chatbot_name': 'TestBot'},
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }
    
    def test_init_creates_service_clients(self, mock_config, monkeypatch):
        """Test that initialization creates service clients."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value=mock_config):
            service = RAGService()
            
            assert service.cache_api is not None
            assert service.chat_api is not None
            assert service.vectorstore_api is not None
            assert service.user_api is not None
            assert service._initialized is False
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_config, monkeypatch):
        """Test successful initialization."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test_key')
        
        mock_agent = MagicMock()
        mock_summary_model = MagicMock()
        
        with patch('RAG.rag_service.load_config', return_value=mock_config), \
             patch('RAG.rag_service.create_agent', return_value=mock_agent), \
             patch('RAG.rag_service.ChatGoogleGenerativeAI', return_value=mock_summary_model), \
             patch.object(RAGService, 'verify_services', new_callable=AsyncMock, return_value={}):
            
            service = RAGService()
            await service.initialize()
            
            assert service._initialized is True
            assert service.agent == mock_agent
            assert service.summary_model == mock_summary_model
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_config, monkeypatch):
        """Test that initialize() is idempotent."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        monkeypatch.setenv('GOOGLE_API_KEY', 'test_key')
        
        mock_agent = MagicMock()
        mock_summary_model = MagicMock()
        
        with patch('RAG.rag_service.load_config', return_value=mock_config), \
             patch('RAG.rag_service.create_agent', return_value=mock_agent), \
             patch('RAG.rag_service.ChatGoogleGenerativeAI', return_value=mock_summary_model), \
             patch.object(RAGService, 'verify_services', new_callable=AsyncMock, return_value={}):
            
            service = RAGService()
            await service.initialize()
            first_init = service._initialized
            
            await service.initialize()
            # Should still be initialized
            assert service._initialized == first_init


class TestRAGServiceStoreMessage:
    """Tests for the store_message() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'prompts': {'summary_template': 'Summarize: {current_summary} {conversation}'},
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            service.summary_model = MagicMock()
            return service
    
    @pytest.mark.asyncio
    async def test_store_message_success(self, rag_service):
        """Test successful message storage."""
        rag_service.chat_api.post = AsyncMock(return_value={"success": True})
        rag_service.cache_api.post = AsyncMock(return_value={"success": True, "needs_summarization": False})
        
        result = await rag_service.store_message(
            session_id="test_session",
            user_id="test_user",
            message_id="test_msg",
            content="Hello",
            role="user",
            timestamp=datetime.now()
        )
        
        assert result["success"] is True
        assert rag_service.chat_api.post.called
        assert rag_service.cache_api.post.called
    
    @pytest.mark.asyncio
    async def test_store_message_with_summarization(self, rag_service):
        """Test message storage with summarization."""
        rag_service.chat_api.post = AsyncMock(return_value={"success": True})
        rag_service.cache_api.post = AsyncMock(return_value={"success": True, "needs_summarization": True})
        rag_service.cache_api.get = AsyncMock(side_effect=[
            [{"role": "user", "content": "Hello"}],  # messages
            {"success": True, "summary": "Previous summary"}  # summary
        ])
        rag_service.summary_model.ainvoke = AsyncMock(return_value=MagicMock(content="New summary"))
        rag_service.cache_api.post = AsyncMock(return_value={"success": True})
        
        result = await rag_service.store_message(
            session_id="test_session",
            user_id="test_user",
            message_id="test_msg",
            content="Hello",
            role="user",
            timestamp=datetime.now()
        )
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_store_message_not_initialized(self, rag_service):
        """Test store_message when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.store_message(
                session_id="test_session",
                user_id="test_user",
                message_id="test_msg",
                content="Hello",
                role="user",
                timestamp=datetime.now()
            )


class TestRAGServiceGetSessionMessages:
    """Tests for the get_session_messages() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            return service
    
    @pytest.mark.asyncio
    async def test_get_session_messages_success(self, rag_service):
        """Test successful retrieval of session messages."""
        messages = [
            {"message_id": "msg1", "role": "user", "content": "Hello", "timestamp": datetime.now()}
        ]
        
        rag_service.chat_api.get = AsyncMock(return_value=messages)
        rag_service.cache_api.get = AsyncMock(return_value={"exists": True})
        
        result = await rag_service.get_session_messages("test_session")
        
        assert result == messages
        assert rag_service.chat_api.get.called
    
    @pytest.mark.asyncio
    async def test_get_session_messages_restores_summary(self, rag_service):
        """Test that missing cache session restores summary."""
        messages = [{"message_id": "msg1", "role": "user", "content": "Hello"}]
        
        rag_service.chat_api.get = AsyncMock(side_effect=[
            messages,  # get-messages
            {"summary": "Test summary"}  # get-summary
        ])
        rag_service.cache_api.get = AsyncMock(return_value={"exists": False})
        rag_service.cache_api.post = AsyncMock(return_value={"success": True})
        
        result = await rag_service.get_session_messages("test_session")
        
        assert result == messages
        assert rag_service.cache_api.post.called  # Should restore summary
    
    @pytest.mark.asyncio
    async def test_get_session_messages_not_initialized(self, rag_service):
        """Test get_session_messages when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.get_session_messages("test_session")


class TestRAGServiceChat:
    """Tests for the chat() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            service.agent = MagicMock()
            service.agent.ainvoke = AsyncMock(return_value={
                'messages': [MagicMock(content="Response")]
            })
            return service
    
    @pytest.mark.asyncio
    async def test_chat_success(self, rag_service):
        """Test successful chat interaction."""
        rag_service.cache_api.get = AsyncMock(side_effect=[
            [],  # messages
            {"success": True, "summary": "Previous summary"}  # summary
        ])
        rag_service._format_conversation = AsyncMock(return_value=[])  # Returns empty list for chat history
        
        response = await rag_service.chat("test_session", "Hello")
        
        assert response == "Response"
        assert rag_service.agent.ainvoke.called
    
    @pytest.mark.asyncio
    async def test_chat_not_initialized(self, rag_service):
        """Test chat when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.chat("test_session", "Hello")


class TestRAGServiceGetSessions:
    """Tests for the get_sessions() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            return service
    
    @pytest.mark.asyncio
    async def test_get_sessions_success(self, rag_service):
        """Test successful retrieval of sessions."""
        sessions = [
            {"session_id": "session1", "created_at": datetime.now(), "title": "Session 1"}
        ]
        
        rag_service.user_api.get = AsyncMock(return_value={"sessions": sessions})
        
        result = await rag_service.get_sessions("test_user")
        
        assert result == sessions
    
    @pytest.mark.asyncio
    async def test_get_sessions_not_initialized(self, rag_service):
        """Test get_sessions when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.get_sessions("test_user")


class TestRAGServiceCreateSession:
    """Tests for the create_session() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            return service
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, rag_service):
        """Test successful session creation."""
        rag_service.user_api.post = AsyncMock(return_value={"success": True})
        
        result = await rag_service.create_session("test_user")
        
        assert "session_id" in result
        assert "created_at" in result
        assert rag_service.user_api.post.called
    
    @pytest.mark.asyncio
    async def test_create_session_failure(self, rag_service):
        """Test session creation failure."""
        rag_service.user_api.post = AsyncMock(return_value={"success": False})
        
        with pytest.raises(Exception, match="Failed to create session"):
            await rag_service.create_session("test_user")
    
    @pytest.mark.asyncio
    async def test_create_session_not_initialized(self, rag_service):
        """Test create_session when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.create_session("test_user")


class TestRAGServiceDeleteSession:
    """Tests for the delete_session() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            service._initialized = True
            return service
    
    @pytest.mark.asyncio
    async def test_delete_session_success(self, rag_service):
        """Test successful session deletion."""
        rag_service.cache_api.delete = AsyncMock(return_value={"success": True})
        rag_service.chat_api.delete = AsyncMock(return_value={"success": True})
        rag_service.user_api.delete = AsyncMock(return_value={"success": True})
        
        result = await rag_service.delete_session("test_user", "test_session")
        
        assert result["success"] is True
        assert rag_service.cache_api.delete.called
        assert rag_service.chat_api.delete.called
        assert rag_service.user_api.delete.called
    
    @pytest.mark.asyncio
    async def test_delete_session_not_initialized(self, rag_service):
        """Test delete_session when service is not initialized."""
        rag_service._initialized = False
        
        with pytest.raises(Exception, match="not initialized"):
            await rag_service.delete_session("test_user", "test_session")


class TestRAGServiceVerifyServices:
    """Tests for the verify_services() method."""
    
    @pytest.fixture
    def rag_service(self, monkeypatch):
        """Create a RAGService instance."""
        monkeypatch.setenv('CACHE_SERVICE_URL', 'http://cache:8000')
        monkeypatch.setenv('CHAT_SERVICE_URL', 'http://chat:8000')
        monkeypatch.setenv('VECTORSTORE_SERVICE_URL', 'http://vectorstore:8000')
        monkeypatch.setenv('USER_SERVICE_URL', 'http://user:8000')
        
        with patch('RAG.rag_service.load_config', return_value={
            'retry': {'max_retries': 3, 'retry_delay': 1.0, 'service_timeout': 30}
        }):
            service = RAGService()
            return service
    
    @pytest.mark.asyncio
    async def test_verify_services_all_healthy(self, rag_service):
        """Test verify_services when all services are healthy."""
        rag_service.cache_api.health_check = AsyncMock(return_value=True)
        rag_service.chat_api.health_check = AsyncMock(return_value=True)
        rag_service.vectorstore_api.health_check = AsyncMock(return_value=True)
        rag_service.user_api.health_check = AsyncMock(return_value=True)
        
        result = await rag_service.verify_services()
        
        assert len(result) == 4
        assert all(status["status"] == "healthy" for status in result.values())
    
    @pytest.mark.asyncio
    async def test_verify_services_some_unhealthy(self, rag_service):
        """Test verify_services when some services are unhealthy."""
        rag_service.cache_api.health_check = AsyncMock(return_value=True)
        rag_service.chat_api.health_check = AsyncMock(return_value=False)
        rag_service.vectorstore_api.health_check = AsyncMock(return_value=True)
        rag_service.user_api.health_check = AsyncMock(return_value=True)
        
        result = await rag_service.verify_services()
        
        assert len(result) == 4
        assert result["Chat Service"]["status"] == "unhealthy"
