import json
import os
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from pathlib import Path
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from RAG.utils import load_config
from RAG.rag_service_pydantic_models import PineconeSearchInput
# from RAG.context import current_jwt_token
from RAG.client import ServiceClient

import logging
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG = load_config()

@tool(
    args_schema=PineconeSearchInput,
    description=f"Searches a personal vector database containing documents about {CONFIG['user'].get('name')}. Use this to find info on {CONFIG['user'].get('name')}'s resume, skills, project reports, and other professional or personal information."
)
async def retrieve_personal_info(query: str) -> str:
    """Retrieve personal information from vector database."""
    try:
        # jwt_token = current_jwt_token.get()
        # headers = {"Authorization": f"Bearer {jwt_token}"} if jwt_token else {}

        # pinecone_service_url = os.getenv("PINECONE_SERVICE_URL")

        service_client = ServiceClient(
            base_url=os.getenv("VECTORSTORE_SERVICE_URL"),
            service_name="VectorStoreService",
            config=CONFIG
        )

        payload = {
            "query": query,
            "top_k": CONFIG['pinecone'].get('top_k', 10),
            "namespace": CONFIG['pinecone'].get('namespace', None),
            
        }
        # with httpx.Client(timeout=CONFIG['retry'].get('service_timeout', 30)) as client:
        #     response = client.post(
        #         f"{pinecone_service_url}/vectorstore/search",
        #         json=payload,
        #         headers=headers,
        #         timeout=CONFIG['retry'].get('service_timeout', 30)
        #     )
        #     response.raise_for_status()
        #     result = response.json()

        result = await service_client.post("/vectorstore/search", json=payload)

        logger.info(f'[Tool Call: Retrieved {len(result.get("results", []))} results from Pinecone for query: "{query}"]')

        return json.dumps(result.get("results", []))

    except httpx.HTTPError as e:
        logger.error(f'[Tool Call: HTTP error accessing Pinecone service: {str(e)}]')
        return json.dumps({
            "success": False,
            "error": f"HTTP error accessing Pinecone service: {str(e)}"
        })
    except Exception as e:
        logger.error(f'[Tool Call: Error accessing vector store: {str(e)}]')
        return json.dumps({
            "success": False,
            "error": f"Error accessing vector store: {str(e)}"
        })

retrieve_personal_info.__doc__ = f"""
        Searches a personal vector database containing documents about {CONFIG['user'].get('name')}. 
        Use this to find info on {CONFIG['user'].get('name')}'s resume, skills, project reports, and other professional or personal information.
        
        IMPORTANT: ONLY use this tool when the user asks specific questions about {CONFIG['user'].get('name')}'s:
        - Professional experience, work history, or employment
        - Projects, research, or technical work
        - Skills, qualifications, or education
        - Resume or CV information
        - Achievements or accomplishments
        
        DO NOT use this tool for:
        - Greetings or casual conversation
        - General knowledge questions
        - Questions about the chatbot itself
        - Workspace/project structure (use get_workspace_structure instead)
        
        Args:
            query: The specific information to search for (e.g., 'What projects has {CONFIG['user'].get('name')} worked on?').

        Returns:
            A JSON string containing retrieved documents and metadata.
    """

def get_tools() -> List:
    """Get the list of available tools."""
    return [retrieve_personal_info]