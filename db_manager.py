"""Cassandra Database Manager for storing chat messages and summaries."""

import os
from datetime import datetime
from typing import List, Dict, Optional
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement
from cassandra.util import uuid_from_time
from config import (
    CASSANDRA_HOSTS, 
    CASSANDRA_PORT, 
    CASSANDRA_KEYSPACE,
    CASSANDRA_REPLICATION_FACTOR
)


class CassandraManager:
    """Manages Cassandra database operations for chat sessions."""
    
    def __init__(self):
        """Initialize Cassandra connection and create schema if needed."""
        self.cluster = None
        self.session = None
        self._connect()
        self._create_schema()
    
    def _connect(self):
        """Establish connection to Cassandra cluster."""
        try:
            # Create cluster connection
            self.cluster = Cluster(
                contact_points=CASSANDRA_HOSTS,
                port=CASSANDRA_PORT
            )
            self.session = self.cluster.connect()
            print(f"[Cassandra] Connected to cluster at {CASSANDRA_HOSTS}")
        except Exception as e:
            print(f"[Cassandra] Error connecting to cluster: {e}")
            raise
    
    def _create_schema(self):
        """Create keyspace and tables if they don't exist."""
        try:
            # Create keyspace
            self.session.execute(f"""
                CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
                WITH replication = {{
                    'class': 'SimpleStrategy',
                    'replication_factor': {CASSANDRA_REPLICATION_FACTOR}
                }}
            """)
            
            # Use the keyspace
            self.session.set_keyspace(CASSANDRA_KEYSPACE)
            
            # Create chat_messages table with user_id
            self.session.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    session_id TEXT,
                    user_id TEXT,
                    message_id TIMEUUID,
                    timestamp TIMESTAMP,
                    role TEXT,
                    content TEXT,
                    PRIMARY KEY (session_id, message_id)
                ) WITH CLUSTERING ORDER BY (message_id DESC)
            """)
            
            # Create session_summaries table with user_id
            self.session.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    summary TEXT,
                    last_updated TIMESTAMP,
                    message_count INT
                )
            """)
            
            # Create sessions table to track user sessions
            self.session.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    created_at TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            
            # Create index for querying sessions by user_id
            try:
                self.session.execute("""
                    CREATE INDEX IF NOT EXISTS sessions_by_user 
                    ON sessions (user_id)
                """)
            except Exception:
                # Index might already exist
                pass
            
            print(f"[Cassandra] Schema created in keyspace '{CASSANDRA_KEYSPACE}'")
        except Exception as e:
            print(f"[Cassandra] Error creating schema: {e}")
            raise
    
    def store_message(self, session_id: str, user_id: str, role: str, content: str) -> bool:
        """
        Store a chat message in Cassandra.
        
        Args:
            session_id: Unique session identifier
            user_id: User identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            bool: Success status
        """
        try:
            message_id = uuid_from_time(datetime.now())
            timestamp = datetime.now()
            
            query = """
                INSERT INTO chat_messages (session_id, user_id, message_id, timestamp, role, content)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.session.execute(query, (session_id, user_id, message_id, timestamp, role, content))
            print(f"[Cassandra] Stored {role} message for session {session_id}")
            return True
        except Exception as e:
            print(f"[Cassandra] Error storing message: {e}")
            return False
    
    def get_session_messages(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieve messages for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries with role, content, and timestamp
        """
        try:
            if limit:
                query = """
                    SELECT role, content, timestamp 
                    FROM chat_messages 
                    WHERE session_id = %s 
                    LIMIT %s
                """
                rows = self.session.execute(query, (session_id, limit))
            else:
                query = """
                    SELECT role, content, timestamp 
                    FROM chat_messages 
                    WHERE session_id = %s
                """
                rows = self.session.execute(query, (session_id,))
            
            messages = [
                {
                    'role': row.role,
                    'content': row.content,
                    'timestamp': row.timestamp.isoformat() if row.timestamp else None
                }
                for row in rows
            ]
            
            # Reverse to get chronological order (table is DESC by default)
            messages.reverse()
            
            print(f"[Cassandra] Retrieved {len(messages)} messages for session {session_id}")
            return messages
        except Exception as e:
            print(f"[Cassandra] Error retrieving messages: {e}")
            return []
    
    def update_session_summary(
        self, 
        session_id: str,
        user_id: str, 
        summary: str, 
        message_count: int
    ) -> bool:
        """
        Update the running summary for a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            summary: Updated summary text
            message_count: Total number of messages in session
            
        Returns:
            bool: Success status
        """
        try:
            last_updated = datetime.now()
            
            query = """
                INSERT INTO session_summaries (session_id, user_id, summary, last_updated, message_count)
                VALUES (%s, %s, %s, %s, %s)
            """
            self.session.execute(query, (session_id, user_id, summary, last_updated, message_count))
            print(f"[Cassandra] Updated summary for session {session_id}")
            return True
        except Exception as e:
            print(f"[Cassandra] Error updating summary: {e}")
            return False
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, any]]:
        """
        Get the current summary for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with summary, last_updated, and message_count or None
        """
        try:
            query = """
                SELECT summary, last_updated, message_count
                FROM session_summaries
                WHERE session_id = %s
            """
            row = self.session.execute(query, (session_id,)).one()
            
            if row:
                return {
                    'summary': row.summary,
                    'last_updated': row.last_updated.isoformat() if row.last_updated else None,
                    'message_count': row.message_count
                }
            return None
        except Exception as e:
            print(f"[Cassandra] Error retrieving summary: {e}")
            return None
    
    def get_message_count(self, session_id: str) -> int:
        """
        Get the total message count for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Total number of messages
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM chat_messages
                WHERE session_id = %s
            """
            row = self.session.execute(query, (session_id,)).one()
            return row.count if row else 0
        except Exception as e:
            print(f"[Cassandra] Error counting messages: {e}")
            return 0
    
    def create_session(self, session_id: str, user_id: str) -> bool:
        """
        Create a new session record.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            bool: Success status
        """
        try:
            now = datetime.now()
            
            query = """
                INSERT INTO sessions (session_id, user_id, created_at, last_active)
                VALUES (%s, %s, %s, %s)
            """
            self.session.execute(query, (session_id, user_id, now, now))
            print(f"[Cassandra] Created session {session_id} for user {user_id}")
            return True
        except Exception as e:
            print(f"[Cassandra] Error creating session: {e}")
            return False
    
    def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last active timestamp for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: Success status
        """
        try:
            now = datetime.now()
            
            query = """
                UPDATE sessions
                SET last_active = %s
                WHERE session_id = %s
            """
            self.session.execute(query, (now, session_id))
            return True
        except Exception as e:
            print(f"[Cassandra] Error updating session activity: {e}")
            return False
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            
        Returns:
            List of session dictionaries
        """
        try:
            query = """
                SELECT session_id, created_at, last_active
                FROM sessions
                WHERE user_id = %s
                LIMIT %s
            """
            rows = self.session.execute(query, (user_id, limit))
            
            sessions = [
                {
                    'session_id': row.session_id,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'last_active': row.last_active.isoformat() if row.last_active else None
                }
                for row in rows
            ]
            
            return sessions
        except Exception as e:
            print(f"[Cassandra] Error getting user sessions: {e}")
            return []
    
    def close(self):
        """Close the Cassandra connection."""
        if self.cluster:
            self.cluster.shutdown()
            print("[Cassandra] Connection closed")
