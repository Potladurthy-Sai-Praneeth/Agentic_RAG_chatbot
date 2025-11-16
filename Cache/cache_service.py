"""Redis Cache Manager for write-through caching of chat messages."""

import redis
from redis.connection import ConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import json
from typing import List, Dict, Optional
import logging
from contextlib import contextmanager
import pathlib
import yaml
import os
from Cache.jwt_utils import *
from Cache.utils import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedisService:
    """Redis Cache Manager for write-through caching of chat messages."""

    def __init__(self):
        self.config = load_config()
        self._initialized = False

        try:
            self.pool = ConnectionPool(
                host=self.config['redis']['host'],
                port=self.config['redis']['port'],
                db=self.config['redis']['db'],
                max_connections=self.config['redis'].get('max_connections', 10),
                decode_responses=self.config['redis'].get('decode_responses', True),
            )
            self.client = redis.Redis(connection_pool=self.pool,
                                    retry= Retry(ExponentialBackoff(base=0.1, cap=2), retries=3),
                                    retry_on_error=[redis.exceptions.ConnectionError, redis.exceptions.TimeoutError])
        
            if not self.health_check():
                raise ConnectionError("Unable to connect to Redis server.")
            self._initialized = True
            logger.info("RedisService initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to create Redis connection pool: {e}")
            raise

    def _get_messages_key(self, session_id: str) -> str:
        """Generate Redis key for session messages list."""
        return f"session:{session_id}:messages"
    
    def _get_summary_key(self, session_id: str) -> str:
        """Generate Redis key for session summary."""
        return f"session:{session_id}:summary"

    def add_message(self, session_id: str, message: Dict) -> bool:
        """Add a message to the session's message list in Redis.
        
        Returns:
            bool: True if summarization is needed (message limit reached), False otherwise.
        """
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")
        
        try:
            messages_key = self._get_messages_key(session_id)
            message_data = json.dumps({'role': message['role'], 'content': message['content']})
            self.client.rpush(messages_key, message_data)
            
            # Get current count for this session
            current_count = self.client.llen(messages_key)

            logger.info(f"Added {message['role']} message to session {session_id} (count: {current_count})")

            if current_count >= self.config['cache']['message_limit']:
                # True indicates that summarization is needed.
                return True
            
            return False

        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error adding message for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error adding message for session {session_id}: {e}")
            raise e

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Retrieve messages from the session's message list in Redis."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            messages_key = self._get_messages_key(session_id)
            if limit is not None:
                message_data_list = self.client.lrange(messages_key, -limit, -1)
            else:
                message_data_list = self.client.lrange(messages_key, 0, -1)

            messages = [json.loads(data) for data in message_data_list]

            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages
        
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error retrieving messages for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving messages for session {session_id}: {e}")
            raise e
        
    
    def get_message_count(self, session_id: str) -> int:
        """Get the count of messages in the session's message list in Redis."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            messages_key = self._get_messages_key(session_id)
            count = self.client.llen(messages_key)

            logger.info(f"Message count for session {session_id}: {count}")
            return count
        
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error getting message count for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error getting message count for session {session_id}: {e}")
            raise e
    
    def trim_cache(self, session_id: str, keep_last: int = None) -> bool:
        """Trim the cache for a session to keep only the last `keep_last` messages."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            messages_key = self._get_messages_key(session_id)
            if keep_last is not None:
                # Remove all messages except the last `keep_last` ones
                current_count = self.client.llen(messages_key)
                if current_count > keep_last:
                    self.client.ltrim(messages_key, -keep_last, -1)
                    logger.info(f"Trimmed cache for session {session_id} to keep last {keep_last} messages.")
                    return True
            return False
                
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error trimming cache for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error trimming cache for session {session_id}: {e}")
            raise e
    
    def update_summary(self, session_id: str, summary: str) -> bool:
        """Update the summary for a session in Redis."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            summary_key = self._get_summary_key(session_id)
            self.client.set(summary_key, summary)

            logger.info(f"Updated summary for session {session_id}.")
            return True
        
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error updating summary for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error updating summary for session {session_id}: {e}")
            raise e
    
    def get_summary(self, session_id: str) -> Optional[str]:
        """Retrieve the summary for a session from Redis."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            summary_key = self._get_summary_key(session_id)
            summary = self.client.get(summary_key)

            logger.info(f"Retrieved summary for session {session_id}.")
            return summary
        
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error retrieving summary for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving summary for session {session_id}: {e}")
            raise e
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all cached data for a session in Redis."""
        if not self._initialized:
            raise RuntimeError("RedisService is not initialized.")

        try:
            messages_key = self._get_messages_key(session_id)
            summary_key = self._get_summary_key(session_id)
            self.client.delete(messages_key)
            self.client.delete(summary_key)

            logger.info(f"Cleared cache for session {session_id}.")
            return True
        
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error clearing cache for session {session_id}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error clearing cache for session {session_id}: {e}")
            raise e

    def health_check(self) -> bool:
        """Check the health of the Redis connection."""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def close(self):
        """Close the Redis connection and connection pool."""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        
        if self.pool:
            try:
                self.pool.disconnect()
                logger.info("Redis connection pool disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting connection pool: {e}")
        
        self._initialized = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()