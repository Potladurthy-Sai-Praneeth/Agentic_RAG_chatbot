"""
Pytest configuration and fixtures for VectorStore tests.
"""
import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from typing import Dict, Any
import io
import zipfile

from VectorStore.vectorstore_service import PineconeService
from VectorStore.document_loader import DocumentLoaderFactory
from langchain_core.documents import Document


@pytest.fixture
def temp_config_file():
    """Create a temporary config.yaml file for testing."""
    config_data = {
        'pinecone': {
            'cloud': 'aws',
            'region': 'us-east-1',
            'top_k': 5,
            'min_nodes': 1,
            'max_nodes': 3
        },
        'models': {
            'embedding': {
                'provider': 'gemini',
                'name': 'models/embedding-001',
                'dimension': 768
            }
        },
        'chunking': {
            'chunk_size': 1500,
            'chunk_overlap': 300
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_pinecone_client():
    """Create a mock Pinecone client."""
    client = MagicMock()
    client.list_indexes = MagicMock(return_value=[])
    client.create_index = MagicMock(return_value=None)
    client.Index = MagicMock(return_value=MagicMock())
    return client


@pytest.fixture
def mock_pinecone_index():
    """Create a mock Pinecone index."""
    index = MagicMock()
    index.describe_index_stats = MagicMock(return_value={
        'total_vector_count': 100,
        'namespaces': {'namespace1': {'vector_count': 50}},
        'dimension': 768
    })
    index.delete = MagicMock(return_value=None)
    return index


@pytest.fixture
def mock_embedding_model():
    """Create a mock embedding model."""
    model = MagicMock()
    model.embedding_dimension = 768
    model.embed_query = MagicMock(return_value=[0.1] * 768)
    return model


@pytest.fixture
def mock_vector_store():
    """Create a mock PineconeVectorStore."""
    vector_store = MagicMock()
    vector_store.add_documents = MagicMock(return_value=None)
    vector_store.similarity_search = MagicMock(return_value=[
        Document(page_content="Test content", metadata={"source": "test.pdf"})
    ])
    return vector_store


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    client = MagicMock()
    client.generate_presigned_url = MagicMock(return_value="https://s3.amazonaws.com/bucket/key?presigned=...")
    return client


@pytest.fixture
def mock_requests_get():
    """Create a mock requests.get for URL downloads."""
    with patch('VectorStore.vectorstore_service.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'test content'])
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def vectorstore_service(temp_config_file, mock_pinecone_client, mock_embedding_model, mock_vector_store, mock_s3_client):
    """Create a PineconeService instance with mocked dependencies."""
    with patch.dict(os.environ, {
        'PINECONE_API_KEY': 'test_api_key',
        'PINECONE_INDEX_NAME': 'test_index',
        'GEMINI_API_KEY': 'test_gemini_key',
        'S3_BUCKET_NAME': 'test_bucket',
        'AWS_ACCESS_KEY_ID': 'test_access_key',
        'AWS_SECRET_ACCESS_KEY': 'test_secret_key',
        'AWS_REGION': 'us-east-1'
    }), \
    patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
    patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
    patch('VectorStore.vectorstore_service.GoogleGenerativeAIEmbeddings') as mock_embeddings_class, \
    patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class, \
    patch('VectorStore.vectorstore_service.boto3.client') as mock_boto3_client:
        
        # Load actual config from temp file
        with open(temp_config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        mock_load_config.return_value = config_data
        mock_pinecone_class.return_value = mock_pinecone_client
        mock_embeddings_class.return_value = mock_embedding_model
        mock_vector_store_class.return_value = mock_vector_store
        mock_boto3_client.return_value = mock_s3_client
        
        service = PineconeService()
        service.client = mock_pinecone_client
        service.embedding_model = mock_embedding_model
        service.vector_store = mock_vector_store
        service.s3_client = mock_s3_client
        
        yield service


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        Document(
            page_content="This is test content 1",
            metadata={"source_file": "test1.pdf", "file_path": "/tmp/test1.pdf"}
        ),
        Document(
            page_content="This is test content 2",
            metadata={"source_file": "test2.pdf", "file_path": "/tmp/test2.pdf"}
        )
    ]


@pytest.fixture
def sample_text_file():
    """Create a sample text file for testing."""
    content = b"This is a test text file content."
    return content


@pytest.fixture
def sample_zip_file():
    """Create a sample zip file for testing."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("test1.txt", "Content of test1.txt")
        zip_file.writestr("test2.txt", "Content of test2.txt")
    zip_buffer.seek(0)
    return zip_buffer.read()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'user_id': 'test_user_12345',
        'email': 'test@example.com'
    }


@pytest.fixture
def sample_ingestion_stats():
    """Sample ingestion statistics."""
    return {
        'total_files': 2,
        'total_documents': 2,
        'total_chunks': 4,
        'success': True,
        'namespace': 'test_namespace'
    }

