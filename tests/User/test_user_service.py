"""
Comprehensive tests for UserService class.
Tests all methods, edge cases, and error scenarios.
"""
import pytest
import asyncpg
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
import asyncio
from User.user_service import UserService
import os
from tests.User.conftest import create_async_context_manager


class TestUserServiceInitialization:
    """Tests for UserService initialization."""
    
    def test_init_with_default_config(self, temp_config_file, monkeypatch):
        """Test initialization with default config path."""
        monkeypatch.setenv('POSTGRES_DB', 'test_db')
        monkeypatch.setenv('POSTGRES_USERNAME', 'test_user')
        monkeypatch.setenv('POSTGRES_PASSWORD', 'test_password')
        
        service = UserService(config_path=temp_config_file)
        
        assert service.db_host == 'localhost'
        assert service.db_port == 5432
        assert service.db_name == 'test_db'
        assert service.db_user == 'test_user'
        assert service.db_password == 'test_password'
        assert service.hex_token_length == 32
        assert service.pool is None
        assert service._initialized is False
    
    def test_init_without_password_raises_error(self, temp_config_file, monkeypatch):
        """Test that initialization without password raises ValueError."""
        monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)
        monkeypatch.setenv('POSTGRES_DB', 'test_db')
        monkeypatch.setenv('POSTGRES_USERNAME', 'test_user')
        # Set POSTGRES_PASSWORD to empty string to ensure it's actually empty
        monkeypatch.setenv('POSTGRES_PASSWORD', '')
        
        with pytest.raises(ValueError, match="Database password must be provided"):
            UserService(config_path=temp_config_file)
    
    def test_init_with_custom_config_path(self, temp_config_file, monkeypatch):
        """Test initialization with custom config path."""
        monkeypatch.setenv('POSTGRES_DB', 'custom_db')
        monkeypatch.setenv('POSTGRES_USERNAME', 'custom_user')
        monkeypatch.setenv('POSTGRES_PASSWORD', 'custom_password')
        
        service = UserService(config_path=temp_config_file)
        assert service.db_config is not None
        assert 'postgres' in service.db_config


class TestUserServiceInitialize:
    """Tests for the initialize() method."""
    
    @pytest.mark.asyncio
    async def test_initialize_creates_pool_and_tables(self, user_service, mock_db_pool, mock_connection):
        """Test that initialize() creates pool and initializes tables."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_db_pool
            
            # Mock connection context manager - acquire() is a regular method that returns an async context manager
            mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
            mock_connection.execute = AsyncMock()
            
            await user_service.initialize()
            
            assert user_service.pool == mock_db_pool
            assert user_service._initialized is True
            assert mock_create_pool.called
            # Verify table creation was called
            assert mock_connection.execute.call_count >= 4  # At least 4 CREATE statements
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, user_service, mock_db_pool, mock_connection):
        """Test that initialize() is idempotent."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_db_pool
            mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
            mock_connection.execute = AsyncMock()
            
            await user_service.initialize()
            first_call_count = mock_create_pool.call_count
            
            await user_service.initialize()
            # Should not create pool again
            assert mock_create_pool.call_count == first_call_count
    
    @pytest.mark.asyncio
    async def test_initialize_handles_errors(self, user_service):
        """Test that initialize() properly handles errors."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                await user_service.initialize()
            
            assert user_service._initialized is False


class TestUserServiceRegisterUser:
    """Tests for the register_user() method."""
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test successful user registration."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.execute = AsyncMock()
        
        user_id = await user_service.register_user(
            sample_user_data['user_email'],
            sample_user_data['username'],
            sample_user_data['password']
        )
        
        assert user_id is not None
        assert isinstance(user_id, str)
        assert len(user_id) > 0
        assert mock_connection.execute.called
    
    @pytest.mark.asyncio
    async def test_register_user_without_pool_raises_error(self, user_service, sample_user_data):
        """Test that register_user() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.register_user(
                sample_user_data['user_email'],
                sample_user_data['username'],
                sample_user_data['password']
            )
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that registering duplicate email returns None."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        # Simulate UniqueViolationError
        error = asyncpg.UniqueViolationError("duplicate key value")
        mock_connection.execute = AsyncMock(side_effect=error)
        
        result = await user_service.register_user(
            sample_user_data['user_email'],
            sample_user_data['username'],
            sample_user_data['password']
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that registering duplicate username returns None."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        error = asyncpg.UniqueViolationError("duplicate key value")
        mock_connection.execute = AsyncMock(side_effect=error)
        
        result = await user_service.register_user(
            sample_user_data['user_email'],
            sample_user_data['username'],
            sample_user_data['password']
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_register_user_other_exception_raises(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that other exceptions during registration are raised."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception, match="Database error"):
            await user_service.register_user(
                sample_user_data['user_email'],
                sample_user_data['username'],
                sample_user_data['password']
            )
    
    @pytest.mark.asyncio
    async def test_register_user_generates_unique_user_id(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that each registration generates a unique user_id."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.execute = AsyncMock()
        
        user_id1 = await user_service.register_user(
            'email1@example.com',
            'user1',
            'password1'
        )
        
        user_id2 = await user_service.register_user(
            'email2@example.com',
            'user2',
            'password2'
        )
        
        assert user_id1 != user_id2
    
    @pytest.mark.asyncio
    async def test_register_user_hashes_password(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that password is hashed before storage."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        captured_args = []
        def capture_execute(*args, **kwargs):
            captured_args.append(args)
        
        mock_connection.execute = AsyncMock(side_effect=capture_execute)
        
        password = "TestPassword123!"
        await user_service.register_user(
            sample_user_data['user_email'],
            sample_user_data['username'],
            password
        )
        
        # Check that password_hash was passed and is different from original password
        assert len(captured_args) > 0
        execute_args = captured_args[0][0]  # SQL query
        execute_params = captured_args[0][1:]  # Parameters
        
        # Password hash should be in parameters (index 3) and salt (index 4)
        password_hash = execute_params[3]
        salt = execute_params[4]
        
        assert password_hash != password
        assert salt is not None
        assert len(salt) > 0


class TestUserServiceLogin:
    """Tests for the login() method."""
    
    @pytest.mark.asyncio
    async def test_login_success_with_username(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test successful login with username."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        # Mock user record - create a proper mock that supports dictionary-like access
        salt = 'salt123'
        password_hash = user_service._hash_password(sample_user_data['password'], salt)
        mock_record = {
            'user_id': sample_user_data['user_id'],
            'password_hash': password_hash,
            'salt': salt
        }
        
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)
        mock_connection.execute = AsyncMock()
        
        user_id = await user_service.login(
            sample_user_data['username'],
            sample_user_data['password']
        )
        
        assert user_id == sample_user_data['user_id']
        assert mock_connection.execute.called  # last_login update
    
    @pytest.mark.asyncio
    async def test_login_success_with_email(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test successful login with email."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        salt = 'salt123'
        password_hash = user_service._hash_password(sample_user_data['password'], salt)
        
        mock_record = {
            'user_id': sample_user_data['user_id'],
            'password_hash': password_hash,
            'salt': salt
        }
        
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)
        mock_connection.execute = AsyncMock()
        
        user_id = await user_service.login(
            sample_user_data['user_email'],
            sample_user_data['password']
        )
        
        assert user_id == sample_user_data['user_id']
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self, user_service, mock_db_pool, mock_connection):
        """Test login when user doesn't exist."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.fetchrow = AsyncMock(return_value=None)
        
        result = await user_service.login('nonexistent@example.com', 'password')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_login_incorrect_password(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test login with incorrect password."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        salt = 'salt123'
        correct_hash = user_service._hash_password('correct_password', salt)
        
        mock_record = {
            'user_id': sample_user_data['user_id'],
            'password_hash': correct_hash,
            'salt': salt
        }
        
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)
        
        result = await user_service.login(
            sample_user_data['username'],
            'wrong_password'
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_login_without_pool_raises_error(self, user_service, sample_user_data):
        """Test that login() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.login(
                sample_user_data['username'],
                sample_user_data['password']
            )
    
    @pytest.mark.asyncio
    async def test_login_updates_last_login(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that login updates last_login timestamp."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        salt = 'salt123'
        password_hash = user_service._hash_password(sample_user_data['password'], salt)
        
        mock_record = {
            'user_id': sample_user_data['user_id'],
            'password_hash': password_hash,
            'salt': salt
        }
        
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)
        mock_connection.execute = AsyncMock()
        
        await user_service.login(
            sample_user_data['username'],
            sample_user_data['password']
        )
        
        # Verify UPDATE was called
        assert mock_connection.execute.called
        update_call = mock_connection.execute.call_args[0][0]
        assert 'UPDATE USERS SET LAST_LOGIN' in update_call.upper()


class TestUserServiceAddSession:
    """Tests for the add_session() method."""
    
    @pytest.mark.asyncio
    async def test_add_session_success(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test successful session addition."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.fetchval = AsyncMock(return_value=True)  # User exists
        mock_connection.execute = AsyncMock()
        
        session_id = await user_service.add_session(
            sample_session_data['session_id'],
            sample_session_data['user_id']
        )
        
        assert session_id == sample_session_data['session_id']
        assert mock_connection.execute.called
    
    @pytest.mark.asyncio
    async def test_add_session_without_pool_raises_error(self, user_service, sample_session_data):
        """Test that add_session() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.add_session(
                sample_session_data['session_id'],
                sample_session_data['user_id']
            )
    
    @pytest.mark.asyncio
    async def test_add_session_handles_exceptions(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test that add_session() properly handles exceptions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.fetchval = AsyncMock(return_value=True)  # User exists
        
        mock_connection.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception, match="Database error"):
            await user_service.add_session(
                sample_session_data['session_id'],
                sample_session_data['user_id']
            )


class TestUserServiceGetSessions:
    """Tests for the get_sessions() method."""
    
    @pytest.mark.asyncio
    async def test_get_sessions_success(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test successful retrieval of sessions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        # Mock session records
        mock_session1 = {
            'session_id': 'session1',
            'created_at': datetime.now()
        }
        
        mock_session2 = {
            'session_id': 'session2',
            'created_at': datetime.now()
        }
        
        mock_connection.fetch = AsyncMock(return_value=[mock_session1, mock_session2])
        
        sessions = await user_service.get_sessions(sample_session_data['user_id'])
        
        assert sessions is not None
        assert len(sessions) == 2
        assert isinstance(sessions, list)
    
    @pytest.mark.asyncio
    async def test_get_sessions_empty_list(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test get_sessions() returns empty list when user has no sessions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.fetch = AsyncMock(return_value=[])
        
        sessions = await user_service.get_sessions(sample_session_data['user_id'])
        
        assert sessions == []
    
    @pytest.mark.asyncio
    async def test_get_sessions_without_pool_raises_error(self, user_service, sample_session_data):
        """Test that get_sessions() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.get_sessions(sample_session_data['user_id'])
    
    @pytest.mark.asyncio
    async def test_get_sessions_handles_exceptions(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test that get_sessions() properly handles exceptions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.fetch = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception, match="Database error"):
            await user_service.get_sessions(sample_session_data['user_id'])


class TestUserServiceDeleteSession:
    """Tests for the delete_session() method."""
    
    @pytest.mark.asyncio
    async def test_delete_session_success(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test successful session deletion."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(return_value="DELETE 1")
        
        result = await user_service.delete_session(
            sample_session_data['user_id'],
            sample_session_data['session_id']
        )
        
        assert result is True
        assert mock_connection.execute.called
    
    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test delete_session() when session doesn't exist."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(return_value="DELETE 0")
        
        result = await user_service.delete_session(
            sample_session_data['user_id'],
            sample_session_data['session_id']
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_session_without_pool_raises_error(self, user_service, sample_session_data):
        """Test that delete_session() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.delete_session(
                sample_session_data['user_id'],
                sample_session_data['session_id']
            )
    
    @pytest.mark.asyncio
    async def test_delete_session_handles_exceptions(self, user_service, mock_db_pool, mock_connection, sample_session_data):
        """Test that delete_session() properly handles exceptions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception, match="Database error"):
            await user_service.delete_session(
                sample_session_data['user_id'],
                sample_session_data['session_id']
            )


class TestUserServiceDeleteUser:
    """Tests for the delete_user() method."""
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test successful user deletion."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(return_value="DELETE 1")
        
        result = await user_service.delete_user(sample_user_data['user_id'])
        
        assert result is True
        assert mock_connection.execute.called
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service, mock_db_pool, mock_connection):
        """Test delete_user() when user doesn't exist."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(return_value="DELETE 0")
        
        result = await user_service.delete_user('nonexistent_user_id')
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_user_without_pool_raises_error(self, user_service, sample_user_data):
        """Test that delete_user() raises error when pool is not initialized."""
        user_service.pool = None
        
        with pytest.raises(RuntimeError, match="Unable to connect to the database"):
            await user_service.delete_user(sample_user_data['user_id'])
    
    @pytest.mark.asyncio
    async def test_delete_user_handles_exceptions(self, user_service, mock_db_pool, mock_connection, sample_user_data):
        """Test that delete_user() properly handles exceptions."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        
        mock_connection.execute = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(Exception, match="Database error"):
            await user_service.delete_user(sample_user_data['user_id'])


class TestUserServiceHealthCheck:
    """Tests for the health_check() method."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, user_service, mock_db_pool, mock_connection):
        """Test successful health check."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.execute = AsyncMock()
        
        result = await user_service.health_check()
        
        assert result is True
        assert mock_connection.execute.called
    
    @pytest.mark.asyncio
    async def test_health_check_no_pool(self, user_service):
        """Test health check when pool is not initialized."""
        user_service.pool = None
        
        result = await user_service.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_database_error(self, user_service, mock_db_pool, mock_connection):
        """Test health check when database query fails."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.execute = AsyncMock(side_effect=Exception("Connection error"))
        
        result = await user_service.health_check()
        
        assert result is False


class TestUserServicePasswordHashing:
    """Tests for password hashing functionality."""
    
    def test_hash_password_creates_hash(self, user_service):
        """Test that _hash_password creates a hash."""
        password = "TestPassword123!"
        salt = "somesalt"
        
        hash1 = user_service._hash_password(password, salt)
        
        assert hash1 is not None
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64 character hex string
    
    def test_hash_password_deterministic(self, user_service):
        """Test that same password and salt produce same hash."""
        password = "TestPassword123!"
        salt = "somesalt"
        
        hash1 = user_service._hash_password(password, salt)
        hash2 = user_service._hash_password(password, salt)
        
        assert hash1 == hash2
    
    def test_hash_password_different_salt_different_hash(self, user_service):
        """Test that different salts produce different hashes."""
        password = "TestPassword123!"
        salt1 = "salt1"
        salt2 = "salt2"
        
        hash1 = user_service._hash_password(password, salt1)
        hash2 = user_service._hash_password(password, salt2)
        
        assert hash1 != hash2
    
    def test_hash_password_different_password_different_hash(self, user_service):
        """Test that different passwords produce different hashes."""
        password1 = "Password1"
        password2 = "Password2"
        salt = "somesalt"
        
        hash1 = user_service._hash_password(password1, salt)
        hash2 = user_service._hash_password(password2, salt)
        
        assert hash1 != hash2


class TestUserServiceContextManager:
    """Tests for async context manager functionality."""
    
    @pytest.mark.asyncio
    async def test_context_manager_initializes_and_closes(self, user_service, mock_db_pool, mock_connection):
        """Test that context manager properly initializes and closes."""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_db_pool
            mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
            mock_db_pool.close = AsyncMock()
            mock_connection.execute = AsyncMock()
            
            async with user_service as service:
                assert service._initialized is True
            
            # Verify close was called
            assert mock_db_pool.close.called
    
    @pytest.mark.asyncio
    async def test_close_method(self, user_service, mock_db_pool):
        """Test the close() method."""
        user_service.pool = mock_db_pool
        user_service._initialized = True
        mock_db_pool.close = AsyncMock()
        
        await user_service.close()
        
        assert mock_db_pool.close.called
        assert user_service._initialized is False
    
    @pytest.mark.asyncio
    async def test_close_without_pool(self, user_service):
        """Test close() when pool is None."""
        user_service.pool = None
        user_service._initialized = True
        
        # Should not raise an error
        await user_service.close()
        
        assert user_service._initialized is False


class TestUserServiceEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_register_user_empty_strings(self, user_service, mock_db_pool, mock_connection):
        """Test register_user() with empty strings."""
        user_service.pool = mock_db_pool
        # Empty strings are now validated and return None
        user_id = await user_service.register_user("", "", "")
        
        assert user_id is None  # Empty strings are now rejected
    
    @pytest.mark.asyncio
    async def test_login_empty_credentials(self, user_service, mock_db_pool, mock_connection):
        """Test login() with empty credentials."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.fetchrow = AsyncMock(return_value=None)
        
        result = await user_service.login("", "")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_sessions_nonexistent_user(self, user_service, mock_db_pool, mock_connection):
        """Test get_sessions() for non-existent user."""
        user_service.pool = mock_db_pool
        mock_db_pool.acquire = MagicMock(return_value=create_async_context_manager(mock_connection))
        mock_connection.fetch = AsyncMock(return_value=[])
        
        sessions = await user_service.get_sessions("nonexistent_user_id")
        
        assert sessions == []

