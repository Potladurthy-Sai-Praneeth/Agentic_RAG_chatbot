from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredMarkdownLoader,
    Docx2txtLoader,
    TextLoader,
    CSVLoader,
    UnstructuredHTMLLoader,
    UnstructuredWordDocumentLoader
)

from pathlib import Path


class DocumentLoaderFactory:
    """Factory class for document loaders with extended file type support."""
    
    SUPPORTED_EXTENSIONS = {
        ".pdf": PyPDFLoader,
        ".md": UnstructuredMarkdownLoader,
        ".docx": Docx2txtLoader,
        ".doc": UnstructuredWordDocumentLoader,
        ".txt": TextLoader,
        ".csv": CSVLoader,
        ".html": UnstructuredHTMLLoader,
        ".htm": UnstructuredHTMLLoader,
    }

    @classmethod
    def get_loader(cls, file_path: str):
        """Get appropriate loader for file extension."""
        ext = Path(file_path).suffix.lower()
        loader_class = cls.SUPPORTED_EXTENSIONS.get(ext)
        
        if not loader_class:
            raise ValueError(
                f"Unsupported file extension: {ext}. "
                f"Supported types: {', '.join(cls.SUPPORTED_EXTENSIONS.keys())}"
            )
        
        return loader_class(file_path)

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """Check if file type is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS
