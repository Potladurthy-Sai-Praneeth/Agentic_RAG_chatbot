"""Asynchronous summarization service for chat conversations."""

import asyncio
import os
from typing import List, Dict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from config import (
    SUMMARY_MODEL_PROVIDER,
    SUMMARY_MODEL_NAME,
    SUMMARIZATION_PROMPT
)

load_dotenv()


class SummarizationService:
    """Handles asynchronous conversation summarization using a smaller LLM."""
    
    def __init__(self):
        """Initialize the summarization model."""
        self.model = self._get_summary_model()
    
    def _get_summary_model(self):
        """Get the configured LLM for summarization."""
        if SUMMARY_MODEL_PROVIDER == 'gemini':
            return ChatGoogleGenerativeAI(
                model=SUMMARY_MODEL_NAME,
                google_api_key=os.getenv("GEMINI_API_KEY"),
                temperature=0.3  # Lower temperature for more focused summaries
            )
        elif SUMMARY_MODEL_PROVIDER == 'openai':
            return ChatOpenAI(
                model=SUMMARY_MODEL_NAME,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.3
            )
        else:
            raise ValueError(f"Unknown summary provider: {SUMMARY_MODEL_PROVIDER}")
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages into a readable conversation string.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            Formatted conversation string
        """
        formatted = []
        for msg in messages:
            role = msg['role'].capitalize()
            content = msg['content']
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
    
    async def summarize_async(
        self, 
        messages: List[Dict[str, str]], 
        previous_summary: str = ''
    ) -> str:
        """
        Asynchronously summarize a list of messages.
        
        Args:
            messages: List of message dictionaries to summarize
            previous_summary: Optional previous summary to build upon
            
        Returns:
            Summary text
        """
        try:
            # Format the conversation
            conversation_text = self._format_conversation(messages)
            
            # # If there's a previous summary, include it in the context
            # if previous_summary:
            #     conversation_text = f"Previous Summary: {previous_summary}\n\nNew Messages:\n{conversation_text}"
            
            # Create the prompt
            prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text,current_summary=previous_summary)
            
            print(f"[Summarization] Starting async summarization of {len(messages)} messages...")
            
            # Run the LLM call asynchronously
            # Note: LangChain models support async invocation
            response = await self.model.ainvoke(prompt)
            
            summary = response.content if hasattr(response, 'content') else str(response)
            
            print(f"[Summarization] Summary generated: {summary[:100]}...")
            return summary
        except Exception as e:
            print(f"[Summarization] Error during summarization: {e}")
            return previous_summary or "Error generating summary"
    
    # def summarize_sync(
    #     self, 
    #     messages: List[Dict[str, str]], 
    #     previous_summary: str = ''
    # ) -> str:
    #     """
    #     Synchronously summarize messages (blocking call).
        
    #     Args:
    #         messages: List of message dictionaries to summarize
    #         previous_summary: Optional previous summary to build upon
            
    #     Returns:
    #         Summary text
    #     """
    #     try:
    #         conversation_text = self._format_conversation(messages)
            
    #         # if previous_summary:
    #         #     conversation_text = f"Previous Summary: {previous_summary}\n\nNew Messages:\n{conversation_text}"
            
    #         prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text,current_summary=previous_summary)
            
    #         print(f"[Summarization] Starting sync summarization of {len(messages)} messages...")
            
    #         response = self.model.invoke(prompt)
    #         summary = response.content if hasattr(response, 'content') else str(response)
            
    #         print(f"[Summarization] Summary generated: {summary[:100]}...")
    #         return summary
    #     except Exception as e:
    #         print(f"[Summarization] Error during summarization: {e}")
    #         return previous_summary or "Error generating summary"


async def trigger_summarization_task(
    summarizer: SummarizationService,
    messages: List[Dict[str, str]],
    previous_summary: str,
    db_manager,
    cache_manager,
    session_id: str,
    user_id: str
) -> None:
    """
    Background task to summarize messages and update storage.
    
    Args:
        summarizer: SummarizationService instance
        messages: Messages to summarize
        previous_summary: Previous summary text
        db_manager: CassandraManager instance
        cache_manager: RedisCache instance
        session_id: Session identifier
        user_id: User identifier
    """
    try:
        # Generate summary asynchronously
        new_summary = await summarizer.summarize_async(messages, previous_summary)
        
        # Update the summary in both Cassandra and Redis
        db_manager.update_session_summary(
            session_id,
            user_id, 
            new_summary, 
            db_manager.get_message_count(session_id)
        )
        cache_manager.update_summary(session_id, new_summary)
        
        # Trim the cache to keep only recent messages
        cache_manager.trim_cache(session_id)
        
        print(f"[Summarization] Completed background summarization for session {session_id}")
    except Exception as e:
        print(f"[Summarization] Error in background task: {e}")
