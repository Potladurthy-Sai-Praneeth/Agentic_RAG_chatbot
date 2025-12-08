import asyncio
import httpx
from httpx import HTTPStatusError
import json
import logging
import os
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from datetime import datetime
import uuid

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain.agents import create_agent
from dotenv import load_dotenv
from RAG.client import ServiceClient
from RAG.utils import load_config
from RAG.tools import get_tools
from RAG.context import current_jwt_token


def serialize_datetime(value):
    """Helper function to ensure datetime objects are converted to ISO format strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class RAGService:
    def __init__(self):

        self.config = load_config()
        self._initialized = False

        # Validate required environment variables
        cache_url = os.getenv("CACHE_SERVICE_URL")
        chat_url = os.getenv("CHAT_SERVICE_URL")
        vectorstore_url = os.getenv("VECTORSTORE_SERVICE_URL")
        user_url = os.getenv("USER_SERVICE_URL")
        
        if not cache_url:
            raise ValueError("CACHE_SERVICE_URL environment variable is required")
        if not chat_url:
            raise ValueError("CHAT_SERVICE_URL environment variable is required")
        if not vectorstore_url:
            raise ValueError("VECTORSTORE_SERVICE_URL environment variable is required")
        if not user_url:
            raise ValueError("USER_SERVICE_URL environment variable is required")

        self.cache_api = ServiceClient(
            base_url=cache_url,
            service_name="CacheService",
            config=self.config
        )

        self.chat_api = ServiceClient(
            base_url=chat_url,
            service_name="ChatService",
            config=self.config
        )

        self.vectorstore_api = ServiceClient(
            base_url=vectorstore_url,
            service_name="VectorStoreService",
            config=self.config
        ) 

        self.user_api = ServiceClient(
            base_url=user_url,
            service_name="UserService",
            config=self.config
        )

        logger.info("RAGService initialized with configuration.")
    
    async def initialize(self):
        if not self._initialized:
            try:
                self.agent = self._get_agent()
                self.summary_model = self._get_model()
                # Verify services asynchronously
                await self.verify_services()
                self._initialized = True
                logger.info("RAGService components initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize RAGService components: {e}")
                raise

    
    def _get_model(self,summary=True):
        """Get the configured summarization LLM."""
        if summary:
            provider = self.config['models']['summary']['provider']
            model_name = self.config['models']['summary']['name']
        else:
            provider = self.config['models']['chat']['provider']
            model_name = self.config['models']['chat']['name']

        if provider == 'gemini':
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                temperature=0.5
            )
        elif provider == 'openai':
            return ChatOpenAI(
                model=model_name,
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.5
            )
        else:
            raise ValueError(f"Unknown summary provider: {provider}")
       
    
    def _get_agent(self):
        system_prompt = self.config['prompts'].get('system_template', '')

        dynamic_names = {
            "person_name": self.config['user'].get('name'),
            "chatbot_name": self.config['user'].get('chatbot_name', 'Viva')
        }

        model = self._get_model(summary=False)

        return create_agent(
            model=model,
            tools=get_tools(),
            system_prompt=system_prompt.format(**dynamic_names),
        )

    async def verify_services(self):
        """Verify connectivity to all dependent services."""
        services = {
            "Cache Service": self.cache_api,
            "Chat Service": self.chat_api,
            "VectorStore Service": self.vectorstore_api,
            "User Service": self.user_api
        }

        response = {}
        
        for name, client in services.items():
            # Add a small delay before checking Pinecone service to allow it to fully start
            if name == "VectorStore Service":
                await asyncio.sleep(3)  # Give VectorStore service time to fully initialize

            is_healthy = await client.health_check()
            if is_healthy:
                logger.info(f"{name} is healthy")
                response[name] = {"status": "healthy", "message": "Service is healthy"}
            else:
                logger.warning(f"{name} is not responding - some features may be limited")
                response[name] = {"status": "unhealthy", "message": "Service is not responding"}
        return response
    
    async def _format_conversation(self, messages: List[Dict[str, str]], text: bool = False) -> str:
        """Format messages into a readable conversation string."""
        formatted = []
        formatted_text = ""
        for msg in messages:
            role = msg['role']
            if role == "user":
                formatted.append(HumanMessage(content=msg['content']))
            elif role == "assistant":
                formatted.append(AIMessage(content=msg['content']))

            if text:
                formatted_text += f"{role}: {msg['content']}\n"
        if text:
            return formatted_text
        return formatted
    
    async def store_message(self, session_id: str, user_id: str, message_id: str, content: str, role: str, timestamp: datetime) -> Dict[str, Any]:
        """Store a chat message for a user."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            chat_payload = {
                "message_id": message_id,
                "role": role,
                "content": content,
                "timestamp": serialize_datetime(timestamp)
            }
            chat_response = await self.chat_api.post(f"/chat/{session_id}/add-message", json=chat_payload)  

            if not chat_response.get("success"):
                logger.error(f"Failed to store message in database for user {user_id}.")
                return {
                    "success": False,
                    "message": "Failed to store message in database."
                }

            logger.info(f"Stored message for user {user_id} with role {role} in database.")

            cache_payload = {
                 "role": role,
                "content": content,
                "timestamp": serialize_datetime(timestamp)
            }

            cache_response = await self.cache_api.post(f"/cache/{session_id}/message", json=cache_payload)

            if not cache_response.get("success"):
                logger.error(f"Failed to cache message for session {session_id}.")
                return {
                    "success": False,
                    "message": "Failed to cache message."
                }

            if chat_response.get("success"):
                if cache_response.get("needs_summarization") and cache_response.get('success'):

                    all_messages = await self.cache_api.get(f"/cache/{session_id}/messages")
                    logger.info(f"Cache messages retrieved for session {session_id}.")

                    current_summary = await self.cache_api.get(f"/cache/{session_id}/get-summary")
                    logger.info(f"Current summary retrieved for session {session_id}.")

                    conversation_text = await self._format_conversation(all_messages, text=True)
                    logger.info(f"Formatted conversation for session {session_id}.")

                    summary_prompt = self.config['prompts'].get('summarization_template', '')
                    logger.info(f"Summary prompt template loaded for session {session_id}.")    

                    if current_summary.get("success") and len(all_messages) > 0:
                        summary_input = summary_prompt.format(
                            current_summary=current_summary.get("summary", "") or "",
                            conversation=conversation_text
                        )

                        summary_response = await self.summary_model.ainvoke(summary_input)
                        logger.info(f"Generated new summary for session {session_id}.")

                        new_summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                        
                        update_summary_payload = {
                            "summary": new_summary,
                            "timestamp": datetime.utcnow().isoformat()
                        }

                        update_summary_response = await self.cache_api.post(f"/cache/{session_id}/update-summary", json=update_summary_payload)
                        trim_cache_response = await self.cache_api.delete(f"/cache/{session_id}/trim")

                        if not update_summary_response.get("success"):
                            logger.error(f"Failed to update cache summary for session {session_id}.")
                        else:
                            logger.info(f"Cache summary updated for session {session_id}.")

                        if not trim_cache_response.get("success"):
                            logger.error(f"Failed to trim cache for session {session_id}.")
                        else:
                            logger.info(f"Cache trimmed for session {session_id}.")
                
                logger.info(f"Message cached successfully for session {session_id}.")
                return {
                    "success": True,
                    "message": f"Message cached successfully for session {session_id}."
                }

        except Exception as e:
            logger.error(f"Error storing message for user {user_id}: {e}")
            raise e
    
    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a session."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            messages_response = await self.chat_api.get(f"/chat/{session_id}/get-messages")

            # Only try to restore summary if there are messages
            if messages_response and len(messages_response) > 0:
                try:
                    session_exist = await self.cache_api.get(f"/cache/{session_id}/session-exists")

                    if not session_exist.get("exists"):
                        logger.info(f"Session {session_id} does not exist in cache. Attempting to restore summary.")
                        
                        try:
                            summary = await self.chat_api.get(f"/chat/{session_id}/get-summary")

                            if summary and summary.get("summary"):
                                payload = {
                                    "summary": summary.get("summary"),
                                    "timestamp": datetime.utcnow().isoformat()
                                }

                                response = await self.cache_api.post(f"/cache/{session_id}/update-summary", json=payload)
                                if response.get("success"):
                                    logger.info(f"Session {session_id} summary restored in cache.")
                                else:
                                    logger.warning(f"Failed to restore summary for session {session_id} in cache.")
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                logger.info(f"No summary exists for session {session_id} - this is normal for new sessions.")
                            else:
                                logger.warning(f"Error retrieving summary for session {session_id}: {e}")
                        except Exception as e:
                            logger.warning(f"Unexpected error while retrieving summary for session {session_id}: {e}")
                except Exception as e:
                    logger.warning(f"Error during summary restoration for session {session_id}: {e}")
            
            logger.info(f"Retrieved {len(messages_response)} messages for session {session_id}.")
            return messages_response

        except Exception as e:
            logger.error(f"Error retrieving messages for session {session_id}: {e}")
            raise e

    async def chat(self, session_id: str, message: str) -> str:
        """Process a chat message and generate a response."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            try:
                history_data = await self.cache_api.get(f"/cache/{session_id}/messages")
                logger.info(f"Retrieved chat history for session {session_id}.")
            except Exception as e:
                logger.error(f"Failed to retrieve chat history for session {session_id}: {e}")
                history_data = []

            try:
                summary_data = await self.cache_api.get(f"/cache/{session_id}/get-summary")
                logger.info(f"Retrieved chat summary for session {session_id}.")
            except Exception as e:
                logger.error(f"Failed to retrieve chat summary for session {session_id}: {e}")
                summary_data = {}

            system_instruction = "You are a helpful RAG assistant."
            if summary_data.get("success") and summary_data.get("summary"):
                system_instruction += f"\n\nPrevious conversation summary: {summary_data.get('summary','')}"

            chat_history_objs = await self._format_conversation(history_data)

            logger.info(f"Formatted chat history for session {session_id}.")

            messages_payload = [
                SystemMessage(content=system_instruction),
                *chat_history_objs,  
                HumanMessage(content=message)
            ]

            response = await self.agent.ainvoke({"messages": messages_payload})

            logger.info(f"Generated response for session {session_id}.")

            # Extract content from the agent response
            # The content can be a string or a list of content blocks
            content = response['messages'][-1].content
            if isinstance(content, list):
                # Extract text from content blocks
                text_parts = [block.get('text', '') if isinstance(block, dict) else str(block) for block in content]
                return ' '.join(text_parts)
            return content
        
        except Exception as e:
            logger.error(f"Error processing chat for session {session_id}: {e}")
            raise e
    
    async def get_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve all sessions for a user."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            sessions_response = await self.user_api.get(f"/user/get-sessions")
            logger.info(f"Retrieved {len(sessions_response.get('sessions', []))} sessions for user {user_id}.")
            return sessions_response.get("sessions", [])

        except Exception as e:
            logger.error(f"Error retrieving sessions for user {user_id}: {e}")
            raise e
    
    async def create_session(self, user_id: str) -> str:
        """Create a new session for a user."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            session_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            logger.info(f"Creating new session {session_id} for user {user_id}.")

            payload = {
                "session_id": session_id,
                "created_at": created_at.isoformat()
            }

            response = await self.user_api.post(f"/user/add-session", json=payload)

            if response.get("success"):
                logger.info(f"Created new session {session_id} for user {user_id}.")
                return {"session_id": session_id, "created_at": created_at}
            else:
                logger.error(f"Failed to create session for user {user_id}.")
                raise Exception("Failed to create session.")

        except Exception as e:
            logger.error(f"Error creating session for user {user_id}: {e}")
            raise e

    async def get_session_title(self, session_id: str) -> Optional[str]:
        """Get the title of a specific session."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            response = await self.user_api.get(f"/user/{session_id}/get-session-title")

            if response.get("success"):
                title = response.get("title")
                logger.info(f"Retrieved title for session {session_id}: {title}")
                return title
            else:
                logger.error(f"Failed to retrieve title for session {session_id}.")
                return None

        except Exception as e:
            logger.error(f"Error retrieving title for session {session_id}: {e}")
            raise e
    
    async def set_session_title(self, session_id: str, title: str) -> Dict[str, Any]:
        """Set the title of a specific session."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            payload = {
                "title": title
            }
            response = await self.user_api.post(f"/user/{session_id}/set-session-title", json=payload)

            if response.get("success"):
                logger.info(f"Set title for session {session_id} to: {title}")
            else:
                logger.error(f"Failed to set title for session {session_id}.")

            return response

        except Exception as e:
            logger.error(f"Error setting title for session {session_id}: {e}")
            raise e
    
    async def clear_cache(self, session_id: str) -> Dict[str, Any]:
        """Clear the cache for a session after the session ends.(Logging out)"""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            response = await self.cache_api.post(f"/cache/{session_id}/clear")

            if response.get("success"):
                logger.info(f"Cleared cache for session {session_id}.")
            else:
                logger.error(f"Failed to clear cache for session {session_id}.")

            return response

        except Exception as e:
            logger.error(f"Error clearing cache for session {session_id}: {e}")
            raise e
    
    async def clear_all_user_caches(self, user_id: str) -> Dict[str, Any]:
        """Clear all cached data for all sessions of a user when they logout."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            # Get all sessions for the user
            sessions = await self.get_sessions(user_id)
            
            cleared_count = 0
            failed_sessions = []
            
            # Clear cache for each session
            for session in sessions:
                session_id = session.get('session_id')
                try:
                    response = await self.cache_api.delete(f"/cache/{session_id}/clear")
                    if response.get("success"):
                        cleared_count += 1
                        logger.info(f"Cleared cache for session {session_id}")
                    else:
                        failed_sessions.append(session_id)
                        logger.warning(f"Failed to clear cache for session {session_id}")
                except Exception as e:
                    failed_sessions.append(session_id)
                    logger.error(f"Error clearing cache for session {session_id}: {e}")
            
            logger.info(f"Cleared {cleared_count} out of {len(sessions)} session caches for user {user_id}")
            
            return {
                "success": True,
                "message": f"Cleared {cleared_count} out of {len(sessions)} session caches",
                "cleared_count": cleared_count,
                "total_sessions": len(sessions),
                "failed_sessions": failed_sessions
            }

        except Exception as e:
            logger.error(f"Error clearing all caches for user {user_id}: {e}")
            raise e
    
    async def delete_session(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """Delete a session for a user."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            # Delete in Cache Service
            cache_response = await self.cache_api.delete(f"/cache/{session_id}/clear")
            if cache_response.get("success"):
                logger.info(f"Cleared cache for session {session_id}.")
            else:
                logger.error(f"Failed to clear cache for session {session_id}.")

            # Delete in Chat Service
            chat_response = await self.chat_api.delete(f"/chat/{session_id}/delete")
            if chat_response.get("success"):
                logger.info(f"Deleted chat for session {session_id}.")
            else:
                logger.error(f"Failed to delete chat for session {session_id}.")

            # Delete in User Service
            response = await self.user_api.delete(f"/user/delete-session", json={"session_id": session_id})

            if response.get("success"):
                logger.info(f"Deleted session {session_id} for user {user_id}.")
            else:
                logger.error(f"Failed to delete session {session_id} for user {user_id}.")

            return {
                "success":True,
                "message": f"Session {session_id} deletion process completed."
            }

        except Exception as e:
            logger.error(f"Error deleting session {session_id} for user {user_id}: {e}")
            raise e
    
    async def health_check(self) -> bool:
        """Health check for RAGService."""
        if not self._initialized:
            logger.error("RAGService not initialized. Call initialize() first.")
            raise Exception("RAGService not initialized. Call initialize() first.")

        try:
            services = [
                self.cache_api,
                self.chat_api,
                self.vectorstore_api,
                self.user_api
            ]

            for client in services:
                is_healthy = await client.health_check()
                if not is_healthy:
                    logger.warning(f"A dependent service is not healthy.")
                    return False

            logger.info("All dependent services are healthy.")
            return True

        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return False

    async def close(self):
        """Clean up resources before shutting down the service."""
        logger.info("Cleaning up RAGService resources.")
        self.agent = None
        self.summary_model = None
        self._initialized = False
        logger.info("RAGService resources cleaned up.")
