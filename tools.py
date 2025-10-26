import json
from dotenv import load_dotenv
from typing import TYPE_CHECKING, List, Dict, Any
from config import *
import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_pinecone import PineconeVectorStore


load_dotenv()


def get_embedding_model():
    """Get the configured embedding model."""
    if EMBEDDING_MODEL_PROVIDER == 'gemini':
        embedding_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME, google_api_key=os.getenv("GEMINI_API_KEY"))
    elif EMBEDDING_MODEL_PROVIDER == 'openai':
        embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME, openai_api_key=os.getenv("OPENAI_API_KEY"))
    return embedding_model



def get_chat_model():
    """Get the configured LangChain chat model."""
    if CHAT_MODEL_PROVIDER == 'gemini':
        return ChatGoogleGenerativeAI(
            model=CHAT_MODEL_NAME,
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.7,
            convert_system_message_to_human=True
        )
    elif CHAT_MODEL_PROVIDER == 'openai':
        return ChatOpenAI(
            model=CHAT_MODEL_NAME,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7
        )
    else:
        raise ValueError(f"Unknown chat provider: {CHAT_MODEL_PROVIDER}")



def get_vectorstore():
    """Get the Pinecone vector store using LangChain."""
    embedding_model = get_embedding_model()
    vectorstore = PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=embedding_model,
        pinecone_api_key=os.getenv("PINECONE_API_KEY")
    )
    return vectorstore



@tool
def retrieve_personal_info(query: str) -> str:
    f"""
    Searches a personal vector database containing documents about {NAME}. 
    Use this to find info on {NAME}'s resume, skills, project reports, and other professional or personal explanations.
    
    Args:
        query: The specific information to search for (e.g., 'What was my role at Company X?').
    
    Returns:
        A JSON string containing 'context' and 'sources'.
    """
    print(f"\n[Tool Call: Running `retrieve_personal_info` with query: '{query}']")

    try:
        vectorstore = get_vectorstore()
        results = vectorstore.similarity_search(query,k=PINECONE_TOP_K)

        if not results:
            print('[Tool Call: No relevant documents found in vector store.]')
            return json.dumps({
                "context": "",
                "sources": [],
                "error": "No relevant documents found."
            })
        
        combined_context = "\n------\n".join([doc.page_content for doc in results])
        sources = [doc.metadata.get('source', 'unknown') for doc in results]

        print(f'[Tool Call: Retrieved {len(results)} documents from vector store.]')
        return json.dumps({
            "context": combined_context,
            "sources": sources
        })

    except Exception as e:
        print(f'[Tool Call: Error accessing vector store: {str(e)}]')
        return json.dumps({
            "context": "",
            "sources": [],
            "error": f"Error accessing vector store: {str(e)}"
        })


def get_tools() -> List:
    """Get the list of available tools."""
    return [retrieve_personal_info]