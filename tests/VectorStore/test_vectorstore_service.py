"""
Comprehensive tests for PineconeService class.
Tests all methods, edge cases, and error scenarios.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock, mock_open
from pathlib import Path
import tempfile
import os
import io
import zipfile
from langchain_core.documents import Document

from VectorStore.vectorstore_service import PineconeService
from VectorStore.document_loader import DocumentLoaderFactory
from tests.VectorStore.conftest import *


class TestPineconeServiceInitialization:
    """Tests for PineconeService initialization."""
    
    def test_init_success(self, temp_config_file, mock_pinecone_client, mock_embedding_model, mock_vector_store, mock_s3_client):
        """Test successful initialization."""
        with patch.dict(os.environ, {
            'PINECONE_API_KEY': 'test_api_key',
            'PINECONE_INDEX_NAME': 'test_index',
            'GEMINI_API_KEY': 'test_gemini_key',
            'S3_BUCKET_NAME': 'test_bucket',
            'AWS_ACCESS_KEY_ID': 'test_access_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret_key'
        }), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
        patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
        patch('VectorStore.vectorstore_service.GoogleGenerativeAIEmbeddings') as mock_embeddings_class, \
        patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class, \
        patch('VectorStore.vectorstore_service.boto3.client') as mock_boto3_client:
            
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            mock_load_config.return_value = config_data
            mock_pinecone_class.return_value = mock_pinecone_client
            mock_embeddings_class.return_value = mock_embedding_model
            mock_vector_store_class.return_value = mock_vector_store
            mock_boto3_client.return_value = mock_s3_client
            
            service = PineconeService()
            
            assert service.config is not None
            assert service.pinecone_api_key == 'test_api_key'
            assert service.pinecone_index_name == 'test_index'
            assert service.client == mock_pinecone_client
            assert service.embedding_model == mock_embedding_model
            assert service.vector_store == mock_vector_store
    
    def test_init_missing_pinecone_api_key(self, temp_config_file):
        """Test initialization fails when PINECONE_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config:
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            mock_load_config.return_value = config_data
            
            with pytest.raises(ValueError, match="PINECONE_API_KEY and PINECONE_INDEX_NAME must be set"):
                PineconeService()
    
    def test_init_missing_pinecone_index_name(self, temp_config_file):
        """Test initialization fails when PINECONE_INDEX_NAME is missing."""
        with patch.dict(os.environ, {'PINECONE_API_KEY': 'test_key'}, clear=True), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config:
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            mock_load_config.return_value = config_data
            
            with pytest.raises(ValueError, match="PINECONE_API_KEY and PINECONE_INDEX_NAME must be set"):
                PineconeService()
    
    def test_init_s3_client_failure(self, temp_config_file, mock_pinecone_client, mock_embedding_model, mock_vector_store):
        """Test initialization when S3 client fails."""
        with patch.dict(os.environ, {
            'PINECONE_API_KEY': 'test_api_key',
            'PINECONE_INDEX_NAME': 'test_index',
            'GEMINI_API_KEY': 'test_gemini_key'
        }), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
        patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
        patch('VectorStore.vectorstore_service.GoogleGenerativeAIEmbeddings') as mock_embeddings_class, \
        patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class, \
        patch('VectorStore.vectorstore_service.boto3.client') as mock_boto3_client:
            
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            mock_load_config.return_value = config_data
            mock_pinecone_class.return_value = mock_pinecone_client
            mock_embeddings_class.return_value = mock_embedding_model
            mock_vector_store_class.return_value = mock_vector_store
            mock_boto3_client.side_effect = Exception("S3 connection failed")
            
            service = PineconeService()
            assert service.s3_client is None


class TestPineconeServiceEmbeddingModel:
    """Tests for embedding model initialization."""
    
    def test_embedding_model_gemini(self, temp_config_file, mock_pinecone_client, mock_vector_store):
        """Test Gemini embedding model initialization."""
        with patch.dict(os.environ, {
            'PINECONE_API_KEY': 'test_api_key',
            'PINECONE_INDEX_NAME': 'test_index',
            'GEMINI_API_KEY': 'test_gemini_key'
        }), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
        patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
        patch('VectorStore.vectorstore_service.GoogleGenerativeAIEmbeddings') as mock_embeddings_class, \
        patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class:
            
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            mock_load_config.return_value = config_data
            mock_pinecone_class.return_value = mock_pinecone_client
            mock_embeddings_class.return_value = MagicMock()
            mock_vector_store_class.return_value = mock_vector_store
            
            service = PineconeService()
            mock_embeddings_class.assert_called_once()
    
    def test_embedding_model_openai(self, temp_config_file, mock_pinecone_client, mock_vector_store):
        """Test OpenAI embedding model initialization."""
        with open(temp_config_file, 'r') as f:
            import yaml
            config_data = yaml.safe_load(f)
        config_data['models']['embedding']['provider'] = 'openai'
        
        with patch.dict(os.environ, {
            'PINECONE_API_KEY': 'test_api_key',
            'PINECONE_INDEX_NAME': 'test_index',
            'OPENAI_API_KEY': 'test_openai_key'
        }), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
        patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
        patch('VectorStore.vectorstore_service.OpenAIEmbeddings') as mock_embeddings_class, \
        patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class:
            
            mock_load_config.return_value = config_data
            mock_pinecone_class.return_value = mock_pinecone_client
            mock_embeddings_class.return_value = MagicMock()
            mock_vector_store_class.return_value = mock_vector_store
            
            service = PineconeService()
            mock_embeddings_class.assert_called_once()
    
    def test_embedding_model_missing_api_key(self, temp_config_file, mock_pinecone_client, mock_vector_store):
        """Test embedding model initialization fails when API key is missing."""
        with patch.dict(os.environ, {
            'PINECONE_API_KEY': 'test_api_key',
            'PINECONE_INDEX_NAME': 'test_index'
        }, clear=True), \
        patch('VectorStore.vectorstore_service.load_config') as mock_load_config, \
        patch('VectorStore.vectorstore_service.PineconeClient') as mock_pinecone_class, \
        patch('VectorStore.vectorstore_service.PineconeVectorStore') as mock_vector_store_class, \
        patch('VectorStore.vectorstore_service.GoogleGenerativeAIEmbeddings') as mock_embeddings_class:
            
            with open(temp_config_file, 'r') as f:
                import yaml
                config_data = yaml.safe_load(f)
            
            mock_load_config.return_value = config_data
            mock_pinecone_class.return_value = mock_pinecone_client
            mock_vector_store_class.return_value = mock_vector_store
            # Mock the embedding class to raise ValueError when API key is missing
            mock_embeddings_class.side_effect = ValueError("GEMINI_API_KEY environment variable not set")
            
            with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
                PineconeService()


class TestPineconeServiceCreateIndex:
    """Tests for create_index method."""
    
    def test_create_index_new(self, vectorstore_service, mock_pinecone_index):
        """Test creating a new index."""
        vectorstore_service.client.list_indexes = MagicMock(return_value=[])
        vectorstore_service.client.create_index = MagicMock()
        
        vectorstore_service.create_index()
        
        vectorstore_service.client.create_index.assert_called_once()
    
    def test_create_index_exists(self, vectorstore_service):
        """Test when index already exists."""
        mock_index = MagicMock()
        mock_index.name = 'test_index'
        vectorstore_service.client.list_indexes = MagicMock(return_value=[mock_index])
        
        # Should not raise exception
        vectorstore_service.create_index()
    
    def test_create_index_error(self, vectorstore_service):
        """Test create_index when error occurs."""
        vectorstore_service.client.list_indexes = MagicMock(side_effect=Exception("Connection error"))
        
        with pytest.raises(Exception, match="Connection error"):
            vectorstore_service.create_index()


class TestPineconeServiceGetIndexStats:
    """Tests for get_index_stats method."""
    
    def test_get_index_stats_success(self, vectorstore_service, mock_pinecone_index):
        """Test successful index stats retrieval."""
        vectorstore_service.client.Index = MagicMock(return_value=mock_pinecone_index)
        
        stats = vectorstore_service.get_index_stats()
        
        assert stats['total_vector_count'] == 100
        assert stats['dimension'] == 768
        assert stats['index_name'] == 'test_index'
        assert 'namespaces' in stats
    
    def test_get_index_stats_error(self, vectorstore_service):
        """Test get_index_stats when error occurs."""
        vectorstore_service.client.Index = MagicMock(side_effect=Exception("Index error"))
        
        with pytest.raises(Exception, match="Index error"):
            vectorstore_service.get_index_stats()


class TestPineconeServiceZipHandling:
    """Tests for zip file handling methods."""
    
    def test_is_zip_file_by_content(self, vectorstore_service):
        """Test _is_zip_file with zip content."""
        zip_content = b'PK\x03\x04'  # ZIP magic bytes
        assert vectorstore_service._is_zip_file(content=zip_content) is True
    
    def test_is_zip_file_by_path(self, vectorstore_service):
        """Test _is_zip_file with zip file path."""
        assert vectorstore_service._is_zip_file(file_path="test.zip") is True
        assert vectorstore_service._is_zip_file(file_path="test.txt") is False
    
    def test_extract_zip_success(self, vectorstore_service, sample_zip_file):
        """Test successful zip extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = vectorstore_service._extract_zip(sample_zip_file, temp_dir)
            
            assert len(files) == 2
            assert any('test1.txt' in f for f in files)
            assert any('test2.txt' in f for f in files)
    
    def test_extract_zip_invalid(self, vectorstore_service):
        """Test zip extraction with invalid zip file."""
        invalid_content = b'Not a zip file'
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(zipfile.BadZipFile):
                vectorstore_service._extract_zip(invalid_content, temp_dir)


class TestPineconeServiceDocumentLoading:
    """Tests for document loading methods."""
    
    def test_load_documents_from_file(self, vectorstore_service):
        """Test loading documents from a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = f.name
        
        try:
            with patch('VectorStore.vectorstore_service.DocumentLoaderFactory.get_loader') as mock_get_loader:
                mock_loader = MagicMock()
                mock_loader.load = MagicMock(return_value=[
                    Document(page_content="Test content", metadata={})
                ])
                mock_get_loader.return_value = mock_loader
                
                docs = vectorstore_service._load_documents_from_file(temp_path)
                
                assert len(docs) == 1
                assert docs[0].page_content == "Test content"
                assert 'source_file' in docs[0].metadata
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_get_files_from_directory(self, vectorstore_service):
        """Test getting files from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            txt_file = os.path.join(temp_dir, "test.txt")
            pdf_file = os.path.join(temp_dir, "test.pdf")
            unsupported_file = os.path.join(temp_dir, "test.xyz")
            
            with open(txt_file, 'w') as f:
                f.write("test")
            with open(pdf_file, 'w') as f:
                f.write("test")
            with open(unsupported_file, 'w') as f:
                f.write("test")
            
            files = vectorstore_service._get_files_from_directory(Path(temp_dir))
            
            # Should only return supported files
            assert len(files) >= 2
            assert any('test.txt' in f for f in files)
            assert any('test.pdf' in f for f in files)
            assert not any('test.xyz' in f for f in files)


class TestPineconeServiceFileContentHandling:
    """Tests for file content handling methods."""
    
    def test_get_files_from_content_zip(self, vectorstore_service, sample_zip_file):
        """Test processing zip file content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = vectorstore_service._get_files_from_content(
                content=sample_zip_file,
                file_name="test.zip",
                temp_dir=temp_dir
            )
            
            assert len(files) == 2
    
    def test_get_files_from_content_single_file(self, vectorstore_service, sample_text_file):
        """Test processing single file content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = vectorstore_service._get_files_from_content(
                content=sample_text_file,
                file_name="test.txt",
                temp_dir=temp_dir
            )
            
            assert len(files) == 1
            assert os.path.exists(files[0])


class TestPineconeServiceDownload:
    """Tests for URL download methods."""
    
    def test_download_from_url_success(self, vectorstore_service, mock_requests_get):
        """Test successful URL download."""
        content = vectorstore_service._download_from_url("https://example.com/file.pdf")
        
        assert content is not None
        assert isinstance(content, bytes)
    
    def test_download_from_url_error(self, vectorstore_service):
        """Test URL download when error occurs."""
        with patch('VectorStore.vectorstore_service.requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.RequestException("Download failed")
            
            with pytest.raises(requests.exceptions.RequestException):
                vectorstore_service._download_from_url("https://example.com/file.pdf")


class TestPineconeServiceIngestion:
    """Tests for document ingestion methods."""
    
    def test_ingest_documents_to_pinecone_success(self, vectorstore_service, sample_documents):
        """Test successful document ingestion."""
        with patch('VectorStore.vectorstore_service.DocumentLoaderFactory.is_supported') as mock_is_supported, \
        patch.object(vectorstore_service, '_load_documents_from_file') as mock_load, \
        patch.object(vectorstore_service.text_splitter, 'split_documents') as mock_split:
            
            mock_is_supported.return_value = True
            mock_load.return_value = sample_documents
            mock_split.return_value = sample_documents
            
            stats = vectorstore_service._ingest_documents_to_pinecone(
                file_paths=["/tmp/test1.pdf"],
                namespace="test_namespace"
            )
            
            assert stats['success'] is True
            assert stats['total_files'] == 1
            assert stats['total_documents'] == 2
            vectorstore_service.vector_store.add_documents.assert_called_once()
    
    def test_ingest_documents_to_pinecone_no_supported_files(self, vectorstore_service):
        """Test ingestion when no supported files."""
        with patch('VectorStore.vectorstore_service.DocumentLoaderFactory.is_supported') as mock_is_supported:
            mock_is_supported.return_value = False
            
            with pytest.raises(ValueError, match="No supported files found"):
                vectorstore_service._ingest_documents_to_pinecone(
                    file_paths=["/tmp/test.xyz"],
                    namespace="test_namespace"
                )
    
    def test_ingest_from_local_path_file(self, vectorstore_service):
        """Test ingestion from local file path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = f.name
        
        try:
            with patch.object(vectorstore_service, '_ingest_documents_to_pinecone') as mock_ingest:
                mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
                
                stats = vectorstore_service.ingest_from_local_path(temp_path)
                
                assert stats['success'] is True
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_ingest_from_local_path_directory(self, vectorstore_service):
        """Test ingestion from local directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            txt_file = os.path.join(temp_dir, "test.txt")
            with open(txt_file, 'w') as f:
                f.write("test")
            
            with patch.object(vectorstore_service, '_ingest_documents_to_pinecone') as mock_ingest:
                mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
                
                stats = vectorstore_service.ingest_from_local_path(temp_dir)
                
                assert stats['success'] is True
    
    def test_ingest_from_local_path_zip(self, vectorstore_service, sample_zip_file):
        """Test ingestion from zip file."""
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(sample_zip_file)
            temp_path = f.name
        
        try:
            with patch.object(vectorstore_service, '_ingest_documents_to_pinecone') as mock_ingest:
                mock_ingest.return_value = {'success': True, 'total_files': 2, 'total_documents': 2, 'total_chunks': 2}
                
                stats = vectorstore_service.ingest_from_local_path(temp_path)
                
                assert stats['success'] is True
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_ingest_from_file_content(self, vectorstore_service, sample_text_file):
        """Test ingestion from file content."""
        with patch.object(vectorstore_service, '_ingest_documents_to_pinecone') as mock_ingest:
            mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
            
            stats = vectorstore_service.ingest_from_file_content(
                file_content=sample_text_file,
                file_name="test.txt"
            )
            
            assert stats['success'] is True
    
    def test_ingest_from_s3_url(self, vectorstore_service, mock_requests_get):
        """Test ingestion from S3 presigned URL."""
        with patch.object(vectorstore_service, '_ingest_documents_to_pinecone') as mock_ingest:
            mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
            
            stats = vectorstore_service.ingest_from_s3_url(
                presigned_url="https://s3.amazonaws.com/bucket/file.pdf?presigned=..."
            )
            
            assert stats['success'] is True
    
    def test_ingest_from_s3_key(self, vectorstore_service):
        """Test ingestion from S3 key."""
        with patch.object(vectorstore_service, 'generate_presigned_download_url') as mock_gen_url, \
        patch.object(vectorstore_service, 'ingest_from_s3_url') as mock_ingest:
            mock_gen_url.return_value = "https://s3.amazonaws.com/bucket/file.pdf?presigned=..."
            mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
            
            stats = vectorstore_service.ingest_from_s3_key(s3_key="uploads/file.pdf")
            
            assert stats['success'] is True
    
    def test_ingest_documents_universal_bytes(self, vectorstore_service, sample_text_file):
        """Test universal ingest_documents with bytes."""
        with patch.object(vectorstore_service, 'ingest_from_file_content') as mock_ingest:
            mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
            
            stats = vectorstore_service.ingest_documents(
                source=sample_text_file,
                file_name="test.txt"
            )
            
            assert stats['success'] is True
    
    def test_ingest_documents_universal_url(self, vectorstore_service, mock_requests_get):
        """Test universal ingest_documents with URL."""
        with patch.object(vectorstore_service, 'ingest_from_s3_url') as mock_ingest:
            mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
            
            stats = vectorstore_service.ingest_documents(
                source="https://s3.amazonaws.com/bucket/file.pdf?presigned=..."
            )
            
            assert stats['success'] is True
    
    def test_ingest_documents_universal_local_path(self, vectorstore_service):
        """Test universal ingest_documents with local path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = f.name
        
        try:
            with patch.object(vectorstore_service, 'ingest_from_local_path') as mock_ingest:
                mock_ingest.return_value = {'success': True, 'total_files': 1, 'total_documents': 1, 'total_chunks': 1}
                
                stats = vectorstore_service.ingest_documents(source=temp_path)
                
                assert stats['success'] is True
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestPineconeServiceSearch:
    """Tests for search method."""
    
    def test_search_success(self, vectorstore_service):
        """Test successful search."""
        results = vectorstore_service.search(
            query="test query",
            top_k=3,
            namespace="test_namespace"
        )
        
        assert len(results) == 1
        assert results[0].page_content == "Test content"
        vectorstore_service.vector_store.similarity_search.assert_called_once()
    
    def test_search_with_default_top_k(self, vectorstore_service):
        """Test search with default top_k from config."""
        results = vectorstore_service.search(query="test query")
        
        # Should use config default (5)
        call_args = vectorstore_service.vector_store.similarity_search.call_args
        assert call_args[1]['k'] == 5
    
    def test_search_with_custom_top_k(self, vectorstore_service):
        """Test search with custom top_k parameter."""
        results = vectorstore_service.search(query="test query", top_k=10)
        
        # Should use provided top_k
        call_args = vectorstore_service.vector_store.similarity_search.call_args
        assert call_args[1]['k'] == 10
    
    def test_search_with_filter(self, vectorstore_service):
        """Test search with metadata filter."""
        filter_dict = {"source_file": "test.pdf"}
        results = vectorstore_service.search(
            query="test query",
            filter=filter_dict
        )
        
        call_args = vectorstore_service.vector_store.similarity_search.call_args
        assert call_args[1]['filter'] == filter_dict
    
    def test_search_error(self, vectorstore_service):
        """Test search when error occurs."""
        vectorstore_service.vector_store.similarity_search = MagicMock(side_effect=Exception("Search error"))
        
        with pytest.raises(Exception, match="Search error"):
            vectorstore_service.search(query="test query")


class TestPineconeServiceNamespaceManagement:
    """Tests for namespace management methods."""
    
    def test_delete_namespace_success(self, vectorstore_service, mock_pinecone_index):
        """Test successful namespace deletion."""
        vectorstore_service.client.Index = MagicMock(return_value=mock_pinecone_index)
        
        result = vectorstore_service.delete_namespace("test_namespace")
        
        assert result is True
        mock_pinecone_index.delete.assert_called_once_with(delete_all=True, namespace="test_namespace")
    
    def test_delete_namespace_error(self, vectorstore_service):
        """Test delete_namespace when error occurs."""
        vectorstore_service.client.Index = MagicMock(side_effect=Exception("Index error"))
        
        with pytest.raises(Exception, match="Index error"):
            vectorstore_service.delete_namespace("test_namespace")


class TestPineconeServiceS3Operations:
    """Tests for S3 operations."""
    
    def test_generate_s3_upload_url_success(self, vectorstore_service):
        """Test successful S3 upload URL generation."""
        result = vectorstore_service.generate_s3_upload_url(
            file_name="test.pdf",
            expiration=3600,
            user_id="user123"
        )
        
        assert 'presigned_url' in result
        assert 's3_key' in result
        assert 'expires_in' in result
        assert 'bucket' in result
        assert 'user123' in result['s3_key']
    
    def test_generate_s3_upload_url_no_s3(self, vectorstore_service):
        """Test S3 upload URL generation when S3 is not configured."""
        vectorstore_service.s3_client = None
        vectorstore_service.s3_bucket_name = None
        
        with pytest.raises(ValueError, match="S3 is not configured"):
            vectorstore_service.generate_s3_upload_url(file_name="test.pdf")
    
    def test_generate_presigned_download_url_success(self, vectorstore_service):
        """Test successful presigned download URL generation."""
        url = vectorstore_service.generate_presigned_download_url(
            s3_key="uploads/file.pdf",
            expiration=3600
        )
        
        assert isinstance(url, str)
        assert len(url) > 0
    
    def test_generate_presigned_download_url_no_s3(self, vectorstore_service):
        """Test presigned download URL generation when S3 is not configured."""
        vectorstore_service.s3_client = None
        vectorstore_service.s3_bucket_name = None
        
        with pytest.raises(ValueError, match="S3 is not configured"):
            vectorstore_service.generate_presigned_download_url(s3_key="uploads/file.pdf")


class TestPineconeServiceCleanup:
    """Tests for cleanup methods."""
    
    def test_cleanup_temp_directory(self, vectorstore_service):
        """Test temporary directory cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            
            assert os.path.exists(temp_dir)
            vectorstore_service._cleanup_temp_directory(temp_dir)
            assert not os.path.exists(temp_dir)
    
    def test_cleanup_temp_directory_nonexistent(self, vectorstore_service):
        """Test cleanup of nonexistent directory."""
        # Should not raise exception
        vectorstore_service._cleanup_temp_directory("/nonexistent/path")

