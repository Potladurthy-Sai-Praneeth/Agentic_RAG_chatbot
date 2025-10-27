import os
import asyncio
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent

from config import *
from tools import *
from db_manager import CassandraManager
from cache_manager import RedisCache
from summarization_service import SummarizationService, trigger_summarization_task
from session_manager import SessionManager

load_dotenv()



class RAGChatbot:
    def __init__(self, user_id: str, session_id: str = None):
        """
        Initialize the RAG chatbot with database and cache integration.
        
        Args:
            user_id: User identifier (required)
            session_id: Optional session ID. If not provided, a new session will be created.
        """
        if not user_id:
            raise ValueError("user_id is required to initialize RAGChatbot")
        
        self.chat_model = get_chat_model()
        self.tools = get_tools()
        self.vectorstore = get_vectorstore()
        
        # Initialize database and cache managers
        self.db_manager = CassandraManager()
        self.cache_manager = RedisCache()
        self.summarizer = SummarizationService()
        self.session_manager = SessionManager()
        
        # Set or create session
        if session_id:
            self.session_manager.current_session_id = session_id
            self.session_manager.current_user_id = user_id
            print(f"[RAGChatbot] Resumed session: {session_id} for user: {user_id}")
        else:
            session_id = self.session_manager.create_new_session(user_id)
            # Create session record in database
            self.db_manager.create_session(session_id, user_id)
        
        # Background task for async summarization
        self.summarization_task = None

        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT_TEMPLATE.format(chatbot_name=CHAT_BOT_NAME, person_name=NAME)),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        self.agent = create_tool_calling_agent(
            llm=self.chat_model,
            tools=self.tools,
            prompt=self.agent_prompt,
        )

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            return_intermediate_steps=False
        )

    def _store_message(self, role: str, content: str) -> None:
        """
        Store message in both Cassandra (persistent) and Redis (cache).
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        session_id = self.session_manager.get_current_session_id()
        user_id = self.session_manager.get_current_user_id()
        
        # Store in Cassandra (persistent database)
        self.db_manager.store_message(session_id, user_id, role, content)
        
        # Update session activity
        self.db_manager.update_session_activity(session_id)
        
        # Store in Redis cache (write-through)
        should_summarize = self.cache_manager.add_message(session_id, role, content)
        
        # Trigger summarization if cache limit reached
        if should_summarize:
            self._trigger_summarization()
    
    def _trigger_summarization(self):
        """Trigger async summarization when cache limit is reached."""
        session_id = self.session_manager.get_current_session_id()
        user_id = self.session_manager.get_current_user_id()

        messages = self.cache_manager.get_messages(session_id, limit=CACHE_MESSAGE_LIMIT)
        
        # Get previous summary (if exists)
        previous_summary = self.cache_manager.get_summary(session_id) or ""
        
        print(f"[RAGChatbot] Triggering async summarization for {len(messages)} NEW messages")
        
        # Create and run the async task in the background
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is already running, schedule the task
            self.summarization_task = asyncio.create_task(
                trigger_summarization_task(
                    self.summarizer,
                    messages,
                    previous_summary,
                    self.db_manager,
                    self.cache_manager,
                    session_id,
                    user_id
                )
            )
        else:
            # If no event loop is running, run it
            loop.run_until_complete(
                trigger_summarization_task(
                    self.summarizer,
                    messages,
                    previous_summary,
                    self.db_manager,
                    self.cache_manager,
                    session_id,
                    user_id
                )
            )

    def _get_chat_history(self) -> List:
        """
        Retrieve chat history from Redis cache and convert to LangChain message format.
        Includes summary of older messages (if available) plus recent k messages.
        
        Returns:
            List of LangChain message objects (HumanMessage/AIMessage only)
        """
        session_id = self.session_manager.get_current_session_id()
        
        # Get the summary of older conversation (if exists)
        summary = self.cache_manager.get_summary(session_id)
        
        # Get recent messages from cache
        messages = self.cache_manager.get_messages(session_id)
        
        # Build chat history
        chat_history = []
        
        # Add summary as an AI message if it exists (not SystemMessage to avoid Gemini error)
        # This works because AI messages can appear anywhere in the history
        if summary:
            summary_message = f"[Context from earlier in our conversation]: {summary}"
            chat_history.append(AIMessage(content=summary_message))
            print(f"[RAGChatbot] Including conversation summary in context")
        
        # Add recent messages
        for msg in messages:
            if msg['role'] == 'user':
                chat_history.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                chat_history.append(AIMessage(content=msg['content']))
        
        return chat_history

    def chat(self, user_input: str) -> str:
        """
        Chat with the RAG chatbot with integrated storage and caching.
        
        Args:
            user_input: User's message
            
        Returns:
            Chatbot's response
        """
        # Store user message
        self._store_message('user', user_input)
        
        # Get chat history from cache/database instead of in-memory
        chat_history = self._get_chat_history()
        
        # Get response from agent
        response = self.agent_executor.invoke({
            "input": user_input,
            "chat_history": chat_history
        })
        
        # Extract the actual output string from the response
        output = response.get("output", str(response))
        
        # Store assistant response
        self._store_message('assistant', output)
        
        return output
    
    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self.session_manager.get_current_session_id()
    
    def get_session_summary(self) -> str:
        """Get the current session summary from cache."""
        session_id = self.session_manager.get_current_session_id()
        return self.cache_manager.get_summary(session_id) or "No summary available yet."
    
    def get_message_history(self, from_cache: bool = True, limit: int = None) -> List[Dict]:
        """
        Get message history from cache or database.
        
        Args:
            from_cache: If True, get from Redis cache; if False, get from Cassandra
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        session_id = self.session_manager.get_current_session_id()
        
        if from_cache:
            return self.cache_manager.get_messages(session_id, limit)
        else:
            return self.db_manager.get_session_messages(session_id, limit)
    
    def close(self) -> None:
        """Close all connections and cleanup."""
        self.db_manager.close()
        self.cache_manager.close()
        self.session_manager.end_session()
        print("[RAGChatbot] All connections closed")