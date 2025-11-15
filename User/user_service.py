import hashlib
import secrets
import os
from datetime import datetime
from typing import Optional, Dict
import asyncpg
import yaml
import pathlib
from dotenv import load_dotenv
import logging
from .utils import load_config

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UserService:
    '''
    Service class for managing user-related operations in the chatbot application.
    Connects to the PostgreSQL database and provides methods for user registration, authentication,
    and other user management tasks.
    '''

    def __init__(self, config_path: Optional[str] = None):
        '''
        Initializes the UserService with database connection parameters.
        Args:
            config_path (Optional[str]): Path to the YAML configuration file. If None, defaults to 'config.yaml' in the current directory.
        '''
        self.db_config = load_config(config_path)
        self.db_host = self.db_config['postgres']['host']
        self.db_port = self.db_config['postgres']['port']
        self.db_name = os.getenv('POSTGRES_DB', 'chatbot_users')
        self.db_user = os.getenv('POSTGRES_USERNAME', 'postgres')
        self.db_password = os.getenv('POSTGRES_PASSWORD', 'password')
        self.hex_token_length = self.db_config.get('hex_token_length', 32)

        if not self.db_password:
            raise ValueError(
                "Database password must be provided either as argument or "
                "through POSTGRES_PASSWORD environment variable"
            )

        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the database connection pool and tables."""
        if self._initialized:
            logger.warning("Database already initialized")
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                min_size=self.db_config['postgres'].get('min_connections', 1),
                max_size=self.db_config['postgres'].get('max_connections', 20)
            )

            await self._init_database()

            self._initialized = True
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    # async def connect(self):
    #     """Connect to the database (alias for initialize() for API compatibility)."""
    #     await self.initialize()
    
    async def _init_database(self):
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(64) PRIMARY KEY,
                        user_email VARCHAR(255) UNIQUE NOT NULL,
                        username VARCHAR(150) UNIQUE NOT NULL,
                        password_hash VARCHAR(256) NOT NULL,
                        salt VARCHAR(64) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP    
                    );
                """)

                await conn.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(user_email);
                """)

                await conn.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
                """)

                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id VARCHAR(64) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    );
                """)

                await conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
                """)

                logger.info("Database tables initialized successfully")

            except Exception as e:
                logger.error(f"Error initializing database tables: {e}")
                raise
        
    async def register_user(self, user_email: str, username: str, password: str) -> Optional[str]:
        """Register a new user in the database."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not user_email or not isinstance(user_email, str) or not user_email.strip():
            logger.error("Invalid email: email cannot be empty")
            return None
        if not username or not isinstance(username, str) or not username.strip():
            logger.error("Invalid username: username cannot be empty")
            return None
        if not password or not isinstance(password, str) or not password.strip():
            logger.error("Invalid password: password cannot be empty")
            return None

        salt = secrets.token_hex(self.hex_token_length)
        password_hash = self._hash_password(password, salt)
        user_id = secrets.token_hex(self.hex_token_length)

        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO users (user_id, user_email, username, password_hash, salt)
                    VALUES ($1, $2, $3, $4, $5);
                """, user_id, user_email, username, password_hash, salt)

                logger.info(f"User {username} registered successfully")
                return user_id

            # User with same email or username already exists
            except asyncpg.UniqueViolationError as e:
                logger.error(f"Registration failed: {e}")
                return None
            
            except Exception as e:
                logger.error(f"Error registering user: {e}")
                raise

    async def login(self, user: str, password: str) -> Optional[str]:
        """Authenticate a user and create a new session."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not user or not isinstance(user, str) or not user.strip():
            logger.error("Invalid user: user identifier cannot be empty")
            return None
        if not password or not isinstance(password, str) or not password.strip():
            logger.error("Invalid password: password cannot be empty")
            return None

        async with self.pool.acquire() as conn:
            try:
                user_record = await conn.fetchrow("""
                    SELECT user_id, password_hash, salt FROM users WHERE username = $1 OR user_email = $1;
                """, user)

                if not user_record:
                    logger.warning(f"Login failed: User {user} not found")
                    return None

                user_id = user_record['user_id']
                stored_hash = user_record['password_hash']
                salt = user_record['salt']

                if stored_hash != self._hash_password(password, salt):
                    logger.warning(f"Login failed: Incorrect password for user {user}")
                    return None

                await conn.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = $1;
                """, user_id)

                logger.info(f"User {user} logged in successfully")
                return user_id

            except Exception as e:
                logger.error(f"Error during login for user {user}: {e}")
                raise

    async def add_session(self, session_id: str, user_id: str) -> Optional[str]:
        """Add a new session for a user."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            logger.error("Invalid session_id: session_id cannot be empty")
            return None
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            logger.error("Invalid user_id: user_id cannot be empty")
            return None

        async with self.pool.acquire() as conn:
            try:
                # Check if user exists before adding session
                user_exists = await conn.fetchval("""
                    SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1);
                """, user_id)
                
                if not user_exists:
                    logger.error(f"Cannot add session: User {user_id} does not exist")
                    return None
                
                await conn.execute("""
                    INSERT INTO user_sessions (session_id, user_id)
                    VALUES ($1, $2);
                """, session_id, user_id)

                logger.info(f"Session {session_id} added for user {user_id}")
                return session_id

            except asyncpg.UniqueViolationError:
                logger.error(f"Session {session_id} already exists")
                return None
            except Exception as e:
                logger.error(f"Error adding session {session_id} for user {user_id}: {e}")
                raise
    
    async def get_sessions(self, user_id: str) -> Optional[list]:
        """Retrieve all sessions for a user."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            logger.error("Invalid user_id: user_id cannot be empty")
            return None

        async with self.pool.acquire() as conn:
            try:
                sessions = await conn.fetch("""
                    SELECT session_id, created_at FROM user_sessions WHERE user_id = $1;
                """, user_id)

                logger.info(f"Retrieved sessions for user {user_id}")
                return [dict(session) for session in sessions]

            except Exception as e:
                logger.error(f"Error retrieving sessions for user {user_id}: {e}")
                raise
    
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a specific session for a user."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            logger.error("Invalid user_id: user_id cannot be empty")
            return False
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            logger.error("Invalid session_id: session_id cannot be empty")
            return False

        async with self.pool.acquire() as conn:
            try:
                result = await conn.execute("""
                    DELETE FROM user_sessions WHERE user_id = $1 AND session_id = $2;
                """, user_id, session_id)

                if result == "DELETE 0":
                    logger.warning(f"No session {session_id} found for user {user_id}")
                    return False

                logger.info(f"Session {session_id} deleted for user {user_id}")
                return True

            except Exception as e:
                logger.error(f"Error deleting session {session_id} for user {user_id}: {e}")
                raise
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and all associated sessions."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            raise RuntimeError("Unable to connect to the database")
        
        # Basic input validation
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            logger.error("Invalid user_id: user_id cannot be empty")
            return False

        async with self.pool.acquire() as conn:
            try:
                result = await conn.execute("""
                    DELETE FROM users WHERE user_id = $1;
                """, user_id)

                if result == "DELETE 0":
                    logger.warning(f"No user found with user_id {user_id}")
                    return False

                logger.info(f"User {user_id} and associated sessions deleted")
                return True

            except Exception as e:
                logger.error(f"Error deleting user {user_id}: {e}")
                raise

    async def health_check(self) -> bool:
        """Check the health of the database connection."""
        if not self.pool:
            logger.error("Database pool is not initialized")
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1;")
            logger.info("Database connection is healthy")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash the password with the given salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    async def close(self):
        """Close all database connections gracefully."""
        if self.pool:
            await self.pool.close()
        self._initialized = False
        logger.info("All database connections closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()