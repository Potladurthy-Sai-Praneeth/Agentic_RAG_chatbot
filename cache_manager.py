"""Redis Cache Manager for write-through caching of chat messages."""

import redis
import json
from typing import List, Dict, Optional
from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_DECODE_RESPONSES,
    CACHE_MESSAGE_LIMIT
)


class RedisCache:
    """Manages Redis cache for chat sessions with write-through strategy."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.current_count = 0
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=REDIS_DECODE_RESPONSES
            )
            # Test connection
            self.redis_client.ping()
            print(f"[Redis] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"[Redis] Error connecting to Redis: {e}")
            raise
    
    def _get_messages_key(self, session_id: str) -> str:
        """Generate Redis key for session messages list."""
        return f"session:{session_id}:messages"
    
    def _get_summary_key(self, session_id: str) -> str:
        """Generate Redis key for session summary."""
        return f"session:{session_id}:summary"
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """
        Add a message to the cache (write-through).
        
        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            bool: Success status
        """
        try:
            messages_key = self._get_messages_key(session_id)
            message_data = json.dumps({'role': role, 'content': content})
            
            # Add message to list
            self.redis_client.rpush(messages_key, message_data)
            
            # Check if we need to trim
            self.current_count += 1 #self.redis_client.llen(messages_key)
            
            print(f"[Redis] Added {role} message to session {session_id} (count: {self.current_count})")
            
            # Return True if we've reached the limit (signals need for summarization)
            if self.current_count >= CACHE_MESSAGE_LIMIT:
                self.current_count = 0  # Reset count after signaling
                return True
            
            return False
        except Exception as e:
            print(f"[Redis] Error adding message: {e}")
            return False
    
    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get messages from cache.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of recent messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        try:
            messages_key = self._get_messages_key(session_id)
            
            if limit:
                # Get the last 'limit' messages
                raw_messages = self.redis_client.lrange(messages_key, -limit, -1)
            else:
                # Get all messages
                raw_messages = self.redis_client.lrange(messages_key, 0, -1)
            
            messages = [json.loads(msg) for msg in raw_messages]
            print(f"[Redis] Retrieved {len(messages)} messages from cache for session {session_id}")
            return messages
        except Exception as e:
            print(f"[Redis] Error retrieving messages: {e}")
            return []
    
    def get_message_count(self, session_id: str) -> int:
        """
        Get the number of messages in cache for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of messages in cache
        """
        try:
            messages_key = self._get_messages_key(session_id)
            count = self.redis_client.llen(messages_key)
            return count
        except Exception as e:
            print(f"[Redis] Error getting message count: {e}")
            return 0
    
    def trim_cache(self, session_id: str, keep_last: int = CACHE_MESSAGE_LIMIT // 2) -> bool:
        """
        Trim the cache to keep only the most recent messages.
        Called after summarization to reduce cache size.
        
        Args:
            session_id: Session identifier
            keep_last: Number of recent messages to keep (default: half of limit)
            
        Returns:
            bool: Success status
        """
        try:
            messages_key = self._get_messages_key(session_id)
            
            # Keep only the last 'keep_last' messages
            # LTRIM keeps elements from start to end index
            # To keep last N: use -N as start and -1 as end
            self.redis_client.ltrim(messages_key, -keep_last, -1)
            
            print(f"[Redis] Trimmed cache for session {session_id}, kept last {keep_last} messages")
            return True
        except Exception as e:
            print(f"[Redis] Error trimming cache: {e}")
            return False
    
    def update_summary(self, session_id: str, summary: str) -> bool:
        """
        Update the running summary for a session.
        
        Args:
            session_id: Session identifier
            summary: Updated summary text
            
        Returns:
            bool: Success status
        """
        try:
            summary_key = self._get_summary_key(session_id)
            self.redis_client.set(summary_key, summary)
            print(f"[Redis] Updated summary for session {session_id}")
            return True
        except Exception as e:
            print(f"[Redis] Error updating summary: {e}")
            return False
    
    def get_summary(self, session_id: str) -> Optional[str]:
        """
        Get the current summary for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary text or None if not found
        """
        try:
            summary_key = self._get_summary_key(session_id)
            summary = self.redis_client.get(summary_key)
            return summary
        except Exception as e:
            print(f"[Redis] Error retrieving summary: {e}")
            return None
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear all cache data for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: Success status
        """
        try:
            messages_key = self._get_messages_key(session_id)
            summary_key = self._get_summary_key(session_id)
            
            self.redis_client.delete(messages_key, summary_key)
            print(f"[Redis] Cleared cache for session {session_id}")
            return True
        except Exception as e:
            print(f"[Redis] Error clearing session: {e}")
            return False
    
    def close(self):
        """Close the Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            print("[Redis] Connection closed")
