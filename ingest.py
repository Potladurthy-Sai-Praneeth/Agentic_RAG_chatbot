import os
from typing import Any
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.schema import Document
import pathlib
import argparse
from config import *


class DocumentLoader(object):
    """Loads in a document with a supported extension."""
    supported_extentions = {
    ".pdf": PyPDFLoader,
    ".md": UnstructuredMarkdownLoader
    }


class IngestData:
    """Ingest data into Pinecone vector store."""
    def __init__(self, folder_path: str) -> None:
        load_dotenv()
        self.folder_path = folder_path
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_index = PINECONE_INDEX_NAME
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.embeddings_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME,google_api_key=self.gemini_api_key)
    
    def load_document(self,temp_filepath: str) -> list[Document]:
        """Load a file and return it as a list of documents."""
        ext = pathlib.Path(temp_filepath).suffix
        loader = DocumentLoader.supported_extentions.get(ext)
        if not loader:
            raise Exception(
            f"Invalid extension type {ext}, cannot load this type of file"
            )
        loader = loader(temp_filepath)
        docs = loader.load()
        return docs

    def ingest(self) -> Any:
        """Ingest data into Pinecone vector store."""
        docs = []
        for filename in os.listdir(self.folder_path):
            temp_filepath = os.path.join(self.folder_path, filename)
            loaded_docs = self.load_document(temp_filepath)
            docs.extend(loaded_docs)
        

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

        texts = text_splitter.split_documents(docs)
        vector_store = PineconeVectorStore.from_documents(
            texts,
            self.embeddings_model,
            index_name=self.pinecone_index,
            pinecone_api_key=self.pinecone_api_key,
        )
        return vector_store

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into Pinecone vector store.")
    parser.add_argument("--data_path", type=str, required=True, help="Path to the folder containing documents to ingest.")
    args = parser.parse_args()

    ingestor = IngestData(folder_path=args.data_path)
    ingestor.ingest()