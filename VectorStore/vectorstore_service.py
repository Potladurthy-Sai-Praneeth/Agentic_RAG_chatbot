import os
import logging
import tempfile
import zipfile
import io
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse
from pathlib import Path
import yaml
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import requests
import shutil
import uuid
from datetime import datetime, timedelta

from VectorStore.utils import load_config
from VectorStore.jwt_utils import *
from VectorStore.document_loader import DocumentLoaderFactory

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from pinecone import Pinecone as PineconeClient, ServerlessSpec

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class PineconeService:
    def __init__(self):
        self.config = load_config()
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

        if not self.pinecone_api_key or not self.pinecone_index_name:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX_NAME must be set in environment variables.")
        
        # S3 Configuration
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        
        self.client = PineconeClient(api_key=self.pinecone_api_key)
        self.embedding_model = self._embedding_model()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config['chunking']['chunk_size'],
            chunk_overlap=self.config['chunking']['chunk_overlap']
        )

        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
            logger.info("S3 client initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize S3 client: {e}. S3 features will not work.")
            self.s3_client = None

        self.vector_store = None
        self._initialize_vector_store()

        logger.info("PineconeService initialized successfully.")

    def _embedding_model(self):
        """Initialize the embedding model based on configuration"""
        model_config = self.config['models']['embedding']
        if model_config.get('provider') == 'gemini':
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.error("GEMINI_API_KEY environment variable not set")
                raise ValueError("GEMINI_API_KEY environment variable not set")
            
            return GoogleGenerativeAIEmbeddings(
                model=model_config['name'],
                google_api_key=api_key
            )
        elif model_config.get('provider') == 'openai':
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            return OpenAIEmbeddings(
                model=model_config['name'],
                api_key=api_key
            )
    
    def _initialize_vector_store(self):
        """Initialize the Pinecone vector store connection"""
        try:
            self.vector_store = PineconeVectorStore(
                index_name=self.pinecone_index_name,
                embedding=self.embedding_model
            )
            logger.info(f"Pinecone vector store initialized for index: {self.pinecone_index_name}")
        except Exception as e:
            logger.error(f"Error initializing Pinecone vector store: {e}")
            raise

    def create_index(self):
        """Create Pinecone index if it doesn't exist"""
        try:
            existing_indexes = [index.name for index in self.client.list_indexes()]
            
            if self.pinecone_index_name not in existing_indexes:
                self.client.create_index(
                    name=self.pinecone_index_name,
                    dimension=self.embedding_model.embedding_dimension,
                    metric="cosine",
                    serverless=ServerlessSpec(
                        cloud=self.config['pinecone']['cloud'], 
                        region=self.config['pinecone']['region']
                    )
                )
                logger.info(f"Created Pinecone index: {self.pinecone_index_name}")
            else:
                logger.info(f"Pinecone index {self.pinecone_index_name} already exists.")
        except Exception as e:
            logger.error(f"Error creating Pinecone index: {e}")
            raise
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Retrieve statistics of the Pinecone index"""
        try:
            index = self.client.Index(self.pinecone_index_name)
            stats = index.describe_index_stats()
            logger.info(f"Retrieved stats for index {self.pinecone_index_name}")
            return {
                "total_vector_count": stats['total_vector_count'],
                "namespaces": stats['namespaces'],
                "dimension": stats['dimension'],
                "index_name": self.pinecone_index_name
            }
        except Exception as e:
            logger.error(f"Error retrieving index stats: {e}")
            raise
    
    def _is_zip_file(self, file_path: str = None, content: bytes = None) -> bool:
        """Check if a file is a zip file by examining its magic bytes or extension."""
        if content:
            return content[:2] == b'PK'
        
        if file_path:
            return Path(file_path).suffix.lower() == '.zip'
        
        return False
    
    def _extract_zip(self, zip_content: bytes, extract_to: str) -> List[str]:
        """Extract zip file and return list of extracted file paths."""
        extracted_files = []
        
        try:
            os.makedirs(extract_to, exist_ok=True)
            
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                file_list = zip_ref.namelist()
                logger.info(f"Extracting {len(file_list)} files from zip archive")
                
                zip_ref.extractall(extract_to)
                
                for file_name in file_list:
                    file_path = os.path.join(extract_to, file_name)
                    if os.path.isfile(file_path):
                        extracted_files.append(file_path)
                
                logger.info(f"Successfully extracted {len(extracted_files)} files from zip")
                return extracted_files
                
        except zipfile.BadZipFile as e:
            logger.error(f"Error: Invalid zip file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting zip file: {e}")
            raise
    
    def _load_documents_from_file(self, file_path: str) -> List[Document]:
        """Load documents from a single file using appropriate loader."""
        try:
            logger.info(f"Loading documents from: {file_path}")
            
            loader = DocumentLoaderFactory.get_loader(file_path)
            documents = loader.load()
            
            file_name = Path(file_path).name
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata['source_file'] = file_name
                doc.metadata['file_path'] = file_path
            
            logger.info(f"Loaded {len(documents)} documents from {file_name}")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading documents from {file_path}: {e}")
            raise

    def _cleanup_temp_directory(self, temp_dir: str):
        """Clean up temporary directory and its contents."""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary directory {temp_dir}: {e}")
    
    def _get_files_from_content(
        self,
        content: bytes,
        file_name: str,
        temp_dir: str
    ) -> List[str]:
        """
        Process file content (single file or zip) and return list of file paths.
        
        Args:
            content: File content as bytes
            file_name: Original file name
            temp_dir: Temporary directory to extract/save files
            
        Returns:
            List of file paths to process
        """
        if self._is_zip_file(content=content):
            logger.info(f"File {file_name} is a zip archive, extracting...")
            return self._extract_zip(content, temp_dir)
        else:
            file_extension = Path(file_name).suffix or '.bin'
            temp_file_path = os.path.join(temp_dir, f"file{file_extension}")
            with open(temp_file_path, 'wb') as f:
                f.write(content)
            logger.info(f"Saved file to: {temp_file_path}")
            return [temp_file_path]
    
    def _get_files_from_directory(self, directory: Path) -> List[str]:
        """Get all supported files from a directory recursively."""
        files = []
        for file_path in directory.rglob('*'):
            if file_path.is_file() and DocumentLoaderFactory.is_supported(str(file_path)):
                files.append(str(file_path))
        logger.info(f"Found {len(files)} supported files in directory")
        return files
    
    def _download_from_url(self, url: str, timeout: int = 300) -> bytes:
        """Download file from URL."""
        try:
            logger.info(f"Downloading file from URL: {url[:50]}...")
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            content = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content.write(chunk)
            
            content.seek(0)
            file_content = content.read()
            logger.info(f"Successfully downloaded {len(file_content)} bytes")
            return file_content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading from URL: {e}")
            raise
    
    def _ingest_documents_to_pinecone(
        self,
        file_paths: List[str],
        namespace: Optional[str]
    ) -> Dict[str, Any]:
        """
        Core ingestion logic: load, chunk, and ingest documents into Pinecone.
        
        Args:
            file_paths: List of file paths to process
            namespace: Optional Pinecone namespace
            
        Returns:
            Dict with ingestion statistics
        """
        stats = {
            'total_files': 0,
            'total_documents': 0,
            'total_chunks': 0,
            'success': False,
            'namespace': namespace
        }
        
        try:
            # Filter supported files
            supported_files = [
                fp for fp in file_paths 
                if DocumentLoaderFactory.is_supported(fp)
            ]
            
            if not supported_files:
                raise ValueError("No supported files found to process")
            
            stats['total_files'] = len(supported_files)
            logger.info(f"Processing {len(supported_files)} supported files")
            
            # Load documents from all files
            all_documents = []
            for file_path in supported_files:
                try:
                    documents = self._load_documents_from_file(file_path)
                    all_documents.extend(documents)
                    stats['total_documents'] += len(documents)
                except Exception as e:
                    logger.error(f"Failed to process file {file_path}: {e}")
                    continue
            
            if not all_documents:
                raise ValueError("No documents were successfully loaded")
            
            # Split into chunks
            logger.info(f"Splitting {len(all_documents)} documents into chunks...")
            chunks = self.text_splitter.split_documents(all_documents)
            stats['total_chunks'] = len(chunks)
            
            # Ingest into Pinecone
            logger.info(f"Ingesting {len(chunks)} chunks into Pinecone")
            self.vector_store.add_documents(
                documents=chunks,
                namespace=namespace
            )
            
            logger.info(
                f"Successfully ingested {stats['total_chunks']} chunks "
                f"from {stats['total_files']} files"
            )
            
            stats['success'] = True
            return stats
            
        except Exception as e:
            logger.error(f"Error during ingestion: {e}")
            stats['error'] = str(e)
            raise
    
    def ingest_from_local_path(
        self,
        source: Union[str, Path],
        namespace: Optional[str] = None,
        cleanup_temp_files: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest documents from a local file, zip archive, or directory.
        
        Args:
            source: Local file path, zip file, or directory
            namespace: Optional Pinecone namespace
            cleanup_temp_files: Whether to cleanup temp files
            
        Returns:
            Dict with ingestion statistics
        """
        temp_dir = None
        
        try:
            source_path = Path(str(source))
            
            if not source_path.exists():
                raise FileNotFoundError(f"Path not found: {source}")
            
            if source_path.is_file() and self._is_zip_file(file_path=str(source_path)):
                # Zip file: extract to temp directory
                temp_dir = tempfile.mkdtemp(prefix='pinecone_zip_')
                logger.info(f"Extracting zip file to: {temp_dir}")
                with open(source_path, 'rb') as f:
                    zip_content = f.read()
                files_to_process = self._extract_zip(zip_content, temp_dir)
            elif source_path.is_dir():
                # Directory: get all supported files
                files_to_process = self._get_files_from_directory(source_path)
            elif source_path.is_file():
                # Single file
                if not DocumentLoaderFactory.is_supported(str(source_path)):
                    raise ValueError(
                        f"Unsupported file type: {source_path.suffix}. "
                        f"Supported: {', '.join(DocumentLoaderFactory.SUPPORTED_EXTENSIONS.keys())}"
                    )
                files_to_process = [str(source_path)]
                logger.info(f"Processing single file: {source_path}")
            else:
                raise ValueError(f"Invalid source: {source}")
            
            # Ingest documents
            return self._ingest_documents_to_pinecone(
                file_paths=files_to_process,
                namespace=namespace
            )
            
        except Exception as e:
            logger.error(f"Error ingesting from local path: {e}")
            raise
        finally:
            if cleanup_temp_files and temp_dir:
                self._cleanup_temp_directory(temp_dir)
    
    def ingest_from_file_content(
        self,
        file_content: bytes,
        file_name: str,
        namespace: Optional[str] = None,
        cleanup_temp_files: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest documents from file content (uploaded via API).
        Handles both single files and zip archives.
        
        Args:
            file_content: File content as bytes
            file_name: Original file name
            namespace: Optional Pinecone namespace
            cleanup_temp_files: Whether to cleanup temp files
            
        Returns:
            Dict with ingestion statistics
        """
        temp_dir = None
        
        try:
            temp_dir = tempfile.mkdtemp(prefix='pinecone_upload_')
            logger.info(f"Processing uploaded file: {file_name}")
            
            # Get file paths (handles both zip and single files)
            files_to_process = self._get_files_from_content(
                content=file_content,
                file_name=file_name,
                temp_dir=temp_dir
            )
            
            # Ingest documents
            return self._ingest_documents_to_pinecone(
                file_paths=files_to_process,
                namespace=namespace
            )
            
        except Exception as e:
            logger.error(f"Error ingesting from file content: {e}")
            raise
        finally:
            if cleanup_temp_files and temp_dir:
                self._cleanup_temp_directory(temp_dir)
    
    def ingest_from_s3_url(
        self,
        presigned_url: str,
        namespace: Optional[str] = None,
        cleanup_temp_files: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest documents from S3 presigned URL.
        Downloads file, processes it (handles zip), and ingests.
        
        Args:
            presigned_url: S3 presigned download URL
            namespace: Optional Pinecone namespace
            cleanup_temp_files: Whether to cleanup temp files
            
        Returns:
            Dict with ingestion statistics
        """
        temp_dir = None
        
        try:
            if not presigned_url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL format: {presigned_url}")
            
            # Download file
            file_content = self._download_from_url(presigned_url)
            
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix='pinecone_s3_')
            
            # Extract filename from URL or use default
            parsed_url = urlparse(presigned_url)
            file_name = Path(parsed_url.path).name or 'downloaded_file'
            
            # Get file paths (handles both zip and single files)
            files_to_process = self._get_files_from_content(
                content=file_content,
                file_name=file_name,
                temp_dir=temp_dir
            )
            
            # Ingest documents
            return self._ingest_documents_to_pinecone(
                file_paths=files_to_process,
                namespace=namespace
            )
            
        except Exception as e:
            logger.error(f"Error ingesting from S3 URL: {e}")
            raise
        finally:
            if cleanup_temp_files and temp_dir:
                self._cleanup_temp_directory(temp_dir)
    
    def ingest_from_s3_key(
        self,
        s3_key: str,
        namespace: Optional[str] = None,
        cleanup_temp_files: bool = True,
        expiration: int = 3600
    ) -> Dict[str, Any]:
        """
        Ingest documents from S3 using object key.
        Generates presigned URL, downloads, and ingests.
        
        Args:
            s3_key: S3 object key
            namespace: Optional Pinecone namespace
            cleanup_temp_files: Whether to cleanup temp files
            expiration: Presigned URL expiration in seconds
            
        Returns:
            Dict with ingestion statistics
        """
        try:
            if not self.s3_bucket_name or not self.s3_client:
                raise ValueError("S3 is not configured")
            
            logger.info(f"Processing S3 object: s3://{self.s3_bucket_name}/{s3_key}")
            
            # Generate presigned download URL
            presigned_url = self.generate_presigned_download_url(
                s3_key=s3_key,
                expiration=expiration
            )
            
            # Ingest from presigned URL
            return self.ingest_from_s3_url(
                presigned_url=presigned_url,
                namespace=namespace,
                cleanup_temp_files=cleanup_temp_files
            )
            
        except Exception as e:
            logger.error(f"Error ingesting from S3 key: {e}")
            raise

    def ingest_documents(
        self, 
        source: Union[str, Path, bytes],
        namespace: Optional[str] = None,
        file_name: Optional[str] = None,
        cleanup_temp_files: bool = True,
        **kwargs  # For backward compatibility
    ) -> Dict[str, Any]:
        """
        Universal entry point for document ingestion.
        Automatically routes to appropriate method based on source type.
        
        Args:
            source: Can be:
                - str/Path: Local file path, directory, or S3 presigned URL
                - bytes: File content uploaded via API
            namespace: Optional Pinecone namespace
            file_name: Required when source is bytes
            cleanup_temp_files: Whether to cleanup temp files
            
        Returns:
            Dict with ingestion statistics
        """
        try:
            # Bytes content (API upload)
            if isinstance(source, bytes):
                if not file_name:
                    raise ValueError("file_name is required when source is bytes")
                return self.ingest_from_file_content(
                    file_content=source,
                    file_name=file_name,
                    namespace=namespace,
                    cleanup_temp_files=cleanup_temp_files
                )
            
            source_str = str(source)
            
            # URL (S3 presigned URL)
            if source_str.startswith(('http://', 'https://')):
                return self.ingest_from_s3_url(
                    presigned_url=source_str,
                    namespace=namespace,
                    cleanup_temp_files=cleanup_temp_files
                )
            
            # Local path (file, zip, or directory)
            else:
                return self.ingest_from_local_path(
                    source=source_str,
                    namespace=namespace,
                    cleanup_temp_files=cleanup_temp_files
                )
                
        except Exception as e:
            logger.error(f"Error in ingest_documents: {e}")
            raise
    
    def search(
        self, 
        query: str, 
        top_k: int = None, 
        namespace: Optional[str] = None,
        filter: Optional[Dict] = None
    ) -> List[Document]:
        """Search for similar documents in Pinecone."""
        # Use provided top_k or fall back to config default
        if top_k is None:
            top_k = self.config['pinecone'].get('top_k', 5)
        
        try:
            results = self.vector_store.similarity_search(
                query=query,
                k=top_k,
                namespace=namespace,
                filter=filter
            )
            return results
        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")
            raise

    def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in a namespace."""
        try:
            index = self.client.Index(self.pinecone_index_name)
            index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted namespace: {namespace}")
            return True
        except Exception as e:
            logger.error(f"Error deleting namespace {namespace}: {e}")
            raise
    
    def generate_s3_upload_url(
        self, 
        file_name: str, 
        expiration: int = 3600,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate presigned URL for uploading file to S3.
        
        Args:
            file_name: Name of file to upload
            expiration: URL expiration in seconds
            content_type: Optional MIME type
            user_id: Optional user ID for organizing files
            
        Returns:
            Dict with presigned_url, s3_key, expires_in, bucket, file_name
        """
        if not self.s3_bucket_name or not self.s3_client:
            raise ValueError("S3 is not configured")
        
        try:
            # Generate unique S3 key
            file_extension = Path(file_name).suffix
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d")
            
            if user_id:
                s3_key = f"uploads/{user_id}/{timestamp}/{unique_id}{file_extension}"
            else:
                s3_key = f"uploads/{timestamp}/{unique_id}{file_extension}"
            
            # Generate presigned URL
            params = {
                'Bucket': self.s3_bucket_name,
                'Key': s3_key,
                'ExpiresIn': expiration
            }
            
            if content_type:
                params['ContentType'] = content_type
            
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params=params,
                HttpMethod='PUT'
            )
            
            logger.info(f"Generated upload URL for {file_name} -> {s3_key}")
            
            return {
                'presigned_url': presigned_url,
                's3_key': s3_key,
                'expires_in': expiration,
                'bucket': self.s3_bucket_name,
                'file_name': file_name
            }
            
        except ClientError as e:
            logger.error(f"Error generating presigned upload URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned upload URL: {e}")
            raise
    
    def generate_presigned_download_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate presigned URL for downloading file from S3.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds
            
        Returns:
            Presigned download URL string
        """
        if not self.s3_bucket_name or not self.s3_client:
            raise ValueError("S3 is not configured")
        
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.s3_bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated download URL for S3 key: {s3_key}")
            return presigned_url
            
        except ClientError as e:
            logger.error(f"Error generating presigned download URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned download URL: {e}")
            raise