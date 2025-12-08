import os
from datetime import datetime
from typing import List, Dict, Optional
from cassandra.cluster import Cluster, Session
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement, ConsistencyLevel
from cassandra.util import uuid_from_time
from uuid import UUID
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
import yaml
import pathlib
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from .utils import load_config

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class ChatService:
    """Manages Cassandra database operations for chat sessions asynchronously."""
    
    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        self.cluster: Optional[Cluster] = None
        self.session: Optional[Session] = None
        self.executor = ThreadPoolExecutor(max_workers=self.config['cassandra'].get('max_workers', 5))
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self._initialized = False
        self.prepared_statements = {}
    
    async def initialize(self):
        """Initialize connection and schema asynchronously."""
        if self._initialized:
            logger.warning("CassandraManager already initialized")
            return
        
        try:
            await self._connect()
            await self._create_schema()
            await self._prepare_statements()
            self._initialized = True
            logger.info("CassandraManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CassandraManager: {e}")
            raise
    
    async def _connect(self):
        try:
            cassandra_host = self.config['cassandra']['host']
            cassandra_port = self.config['cassandra']['port']

            self.cluster = Cluster(
                contact_points=[cassandra_host],
                port=cassandra_port,
                load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
                protocol_version=4
            )
            self.session = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cluster.connect
            )
            logger.info("Connected to Cassandra cluster")
        except Exception as e:
            logger.error(f"Failed to connect to Cassandra: {e}")
            raise
    
    async def _create_schema(self):
        """Create keyspace and tables if they do not exist."""
        try:
            keyspace = os.getenv("CASSANDRA_KEYSPACE_NAME")
            replication_factor = self.config['cassandra'].get('replication_factor', 1)
            
            create_keyspace_cql = f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH REPLICATION = {{ 'class' : 'SimpleStrategy', 'replication_factor' : {replication_factor} }};
            """
            await self.loop.run_in_executor(
                self.executor,
                lambda: self.session.execute(create_keyspace_cql)
            )
            logger.info(f"Keyspace '{keyspace}' ensured")
            
            self.session.set_keyspace(keyspace)

            chat_table_name = os.getenv("CASSANDRA_CHAT_TABLE_NAME")
            summary_table_name = os.getenv("CASSANDRA_SUMMARY_TABLE_NAME")

            create_chat_table_cql = f"""
            CREATE TABLE IF NOT EXISTS {chat_table_name} (
                            session_id TEXT,
                            user_id TEXT,
                            message_id TIMEUUID,
                            timestamp TIMESTAMP,
                            role TEXT,
                            content TEXT,
                            PRIMARY KEY (session_id, message_id)
                        ) WITH CLUSTERING ORDER BY (message_id DESC);
            """
            await self.loop.run_in_executor(
                self.executor,
                lambda: self.session.execute(create_chat_table_cql)
            )
            logger.info(f"Table '{chat_table_name}' ensured")

            create_summary_table_cql = f"""
            CREATE TABLE IF NOT EXISTS {summary_table_name} (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT,
                        summary TEXT,
                        last_updated TIMESTAMP,
                        message_count INT
                        );
            """

            await self.loop.run_in_executor(
                self.executor,
                lambda: self.session.execute(create_summary_table_cql)
            )

            logger.info(f"Table '{summary_table_name}' ensured")

            logger.info("Schema creation completed")
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise
    
    async def _prepare_statements(self):
        """Prepare frequently used CQL statements."""
        try:
            chat_table_name = os.getenv("CASSANDRA_CHAT_TABLE_NAME")
            summary_table_name = os.getenv("CASSANDRA_SUMMARY_TABLE_NAME")

            insert_chat_cql = f"""
            INSERT INTO {chat_table_name} (session_id, user_id, message_id, timestamp, role, content)
            VALUES (?, ?, ?, ?, ?, ?);
            """
            select_chat_cql = f"""
            SELECT role, content, message_id, timestamp
            FROM {chat_table_name}
            WHERE session_id = ?;
            """
            select_chat_cql_limit = f"""
            SELECT role, content, message_id, timestamp
            FROM {chat_table_name}
            WHERE session_id = ?
            LIMIT ?;
            """
            delete_session_chat_cql = f"""
            DELETE FROM {chat_table_name}
            WHERE session_id = ?;
            """
            get_chat_message_count_cql = f"""
            SELECT COUNT(*) FROM {chat_table_name}
            WHERE session_id = ?;
            """

            insert_summary_cql = f"""
            INSERT INTO {summary_table_name} (session_id, user_id, summary, last_updated, message_count)
            VALUES (?, ?, ?, ?, ?);
            """
            select_summary_cql = f"""
            SELECT session_id, user_id, summary, last_updated, message_count
            FROM {summary_table_name}
            WHERE session_id = ?;
            """
            # update_summary_cql = f"""
            # UPDATE {summary_table_name}
            # SET summary = ?, last_updated = ?, message_count = ?
            # WHERE session_id = ?;
            # """
            delete_summary_cql = f"""
            DELETE FROM {summary_table_name}
            WHERE session_id = ?;
            """
            # get_summary_message_count_cql = f"""
            # SELECT message_count FROM {summary_table_name}
            # WHERE session_id = ?;
            # """

            self.prepared_statements['insert_message'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(insert_chat_cql))
            self.prepared_statements['select_messages'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(select_chat_cql))
            self.prepared_statements['delete_session_messages'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(delete_session_chat_cql))
            self.prepared_statements['get_chat_message_count'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(get_chat_message_count_cql))
            self.prepared_statements['select_messages_limit'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(select_chat_cql_limit))

            self.prepared_statements['insert_summary'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(insert_summary_cql))
            self.prepared_statements['select_summary'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(select_summary_cql))
            self.prepared_statements['delete_summary'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(delete_summary_cql))
            # self.prepared_statements['get_summary_message_count'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(get_summary_message_count_cql))
            # self.prepared_statements['update_summary'] = await self.loop.run_in_executor(self.executor, lambda: self.session.prepare(update_summary_cql))

            logger.info("Prepared statements created")
        except Exception as e:
            logger.error(f"Failed to prepare statements: {e}")
            raise

    async def store_message(self, session_id: str, user_id: str, message_id: str, role: str, content: str, timestamp: Optional[datetime] = None):
        """Store a chat message asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")
        
        try:
            if timestamp is None:
                timestamp = datetime.now()
            # Convert string UUID to UUID object for Cassandra
            try:
                message_id_uuid = UUID(message_id)
            except ValueError as e:
                logger.error(f"Invalid message_id format: {message_id}")
                raise ValueError(f"Invalid message_id format: {message_id}") from e

            def _execute():
                future = self.session.execute_async(
                    self.prepared_statements['insert_message'],
                    (session_id, user_id, message_id_uuid, timestamp, role, content)
                )
                return future.result()
            await self.loop.run_in_executor(self.executor, _execute)
            logger.info(f"Stored message for session_id={session_id}, message_id={message_id}")
            return {
                "message_id": str(message_id),
                "timestamp": timestamp
                }
        
        except Exception as e:
            logger.error(f"Failed to store message: {e}")
            raise

    async def get_messages(self, session_id: str, limit: int = None) -> List[Dict]:
        """Retrieve messages for a given session asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")

        try:
            def _execute():
                if limit is not None:
                    future = self.session.execute_async(
                        self.prepared_statements['select_messages_limit'],
                        (session_id, limit)
                    )
                else:
                    future = self.session.execute_async(
                        self.prepared_statements['select_messages'],
                        (session_id,)
                    )
                return future.result()

            rows = await self.loop.run_in_executor(self.executor, _execute)
            messages = [
                {
                    "role": row.role,
                    "content": row.content,
                    "message_id": str(row.message_id),  # Convert UUID to string for Pydantic validation
                    "timestamp": row.timestamp
                }
                for row in rows
            ]
            # Reverse to get oldest messages first (Cassandra returns DESC order)
            messages.reverse()
            logger.info(f"Retrieved {len(messages)} messages for session_id={session_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to retrieve messages: {e}")
            raise
    
    async def get_summary(self, session_id: str) -> Optional[Dict]:
        """Retrieve session summary asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")

        try:
            def _execute():
                future = self.session.execute_async(
                    self.prepared_statements['select_summary'],
                    (session_id,)
                )
                return future.result()

            row = await self.loop.run_in_executor(self.executor, _execute)
            result = row.one()
            if result:
                summary = {
                    "session_id": result.session_id,
                    "user_id": result.user_id,
                    "summary": result.summary,
                    "last_updated": result.last_updated,
                    "message_count": result.message_count
                }
                logger.info(f"Retrieved summary for session_id={session_id}")
                return summary
            else:
                logger.info(f"No summary found for session_id={session_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to retrieve summary: {e}")
            raise
    
    async def insert_summary(self, session_id: str, user_id: str, summary: str, message_count: int, timestamp: Optional[datetime] = None):
        """Insert a new session summary asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")
        
        try:
            if timestamp is None:
                timestamp = datetime.now()
            last_updated = timestamp

            def _execute():
                future = self.session.execute_async(
                    self.prepared_statements['insert_summary'],
                    (session_id, user_id, summary, last_updated, message_count)
                )
                return future.result()
            await self.loop.run_in_executor(self.executor, _execute)
            logger.info(f"Inserted summary for session_id={session_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to insert summary: {e}")
            raise
    
    # async def update_summary(self, session_id: str, user_id: str, summary: str, message_count: int):
    #     """Store or update session summary asynchronously."""
    #     if not self._initialized:
    #         logger.error("CassandraManager not initialized. Call initialize() first.")
    #         raise Exception("CassandraManager not initialized. Call initialize() first.")
        
    #     try:
    #         last_updated = datetime.now()

    #         def _execute():
    #             future = self.session.execute_async(
    #                 self._prepared_statements['update_summary'],
    #                 (summary, last_updated, message_count, session_id)
    #             )
    #             return future.result()
    #         await self.loop.run_in_executor(self.executor, _execute)
    #         logger.info(f"Stored/Updated summary for session_id={session_id}")
    #         return True
        
    #     except Exception as e:
    #         logger.error(f"Failed to store/update summary: {e}")
    #         raise
    
    async def get_message_count(self, session_id: str) -> int:
        """Get the message count for a given session asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")

        try:
            def _execute():
                future = self.session.execute_async(
                    self.prepared_statements['get_chat_message_count'],
                    (session_id,)
                )
                return future.result()

            row = await self.loop.run_in_executor(self.executor, _execute)
            count = row.one()[0]
            logger.info(f"Message count for session_id={session_id} is {count}")
            return count

        except Exception as e:
            logger.error(f"Failed to get message count: {e}")
            raise

    # async def get_summary_message_count(self, session_id: str) -> int:
    #     """Get the message count from summary for a given session asynchronously."""
    #     if not self._initialized:
    #         logger.error("CassandraManager not initialized. Call initialize() first.")
    #         raise Exception("CassandraManager not initialized. Call initialize() first.")

    #     try:
    #         def _execute():
    #             future = self.session.execute_async(
    #                 self._prepared_statements['get_summary_message_count'],
    #                 (session_id,)
    #             )
    #             return future.result()

    #         row = await self.loop.run_in_executor(self.executor, _execute)
    #         count = row.one()[0]
    #         logger.info(f"Summary message count for session_id={session_id} is {count}")
    #         return count

    #     except Exception as e:
    #         logger.error(f"Failed to get summary message count: {e}")
    #         raise

    async def delete_session(self, session_id: str):
        """Delete all messages and summary for a given session asynchronously."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            raise Exception("CassandraManager not initialized. Call initialize() first.")

        try:
            def _execute_delete_messages():
                future = self.session.execute_async(
                    self.prepared_statements['delete_session_messages'],
                    (session_id,)
                )
                return future.result()

            def _execute_delete_summary():
                future = self.session.execute_async(
                    self.prepared_statements['delete_summary'],
                    (session_id,)
                )
                return future.result()

            await self.loop.run_in_executor(self.executor, _execute_delete_messages)
            await self.loop.run_in_executor(self.executor, _execute_delete_summary)

            logger.info(f"Deleted session data for session_id={session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session data: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Perform a health check on the Cassandra connection."""
        if not self._initialized:
            logger.error("CassandraManager not initialized. Call initialize() first.")
            return False
        
        try:
            def _execute():
                future = self.session.execute_async("SELECT now() FROM system.local;")
                return future.result()
            await self.loop.run_in_executor(self.executor, _execute)
            logger.info("Cassandra health check passed")
            return True
        except Exception as e:
            logger.error(f"Cassandra health check failed: {e}")
            return False


    async def close(self):
        """Close the Cassandra connection gracefully."""
        if self.cluster:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cluster.shutdown
            )
            logger.info("Cassandra connection closed")
        
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("Thread pool executor shutdown")
        
        self._initialized = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()