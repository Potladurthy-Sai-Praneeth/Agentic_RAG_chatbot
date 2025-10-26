# RAG Chatbot - Personal Information Assistant

A sophisticated Retrieval-Augmented Generation (RAG) chatbot that answers questions about personal documents, resumes, projects, and professional information. Built with LangChain, Pinecone, and Google's Gemini AI.

## 🤖 What is RAG?

**Retrieval-Augmented Generation (RAG)** is an AI framework that enhances Large Language Models (LLMs) by combining them with external knowledge retrieval. Instead of relying solely on the model's training data, RAG:

1. **Retrieves** relevant information from a knowledge base (vector database)
2. **Augments** the user's query with this retrieved context
3. **Generates** accurate, contextual responses based on the retrieved information


## 🔄 How This Project Works

This RAG chatbot follows a two-phase workflow:

### Phase 1: Data Ingestion (One-time Setup)
```
Documents (PDF/MD) → Chunking → Embeddings → Vector Store (Pinecone)
```

1. **Document Loading**: Reads PDF and Markdown files from a specified folder
2. **Text Splitting**: Breaks documents into manageable chunks (1000 chars with 200 overlap)
3. **Embedding Generation**: Converts text chunks into vector representations using Google's embedding model
4. **Vector Storage**: Stores embeddings in Pinecone for fast similarity search

### Phase 2: Query Answering (Runtime)
```
User Query → Embedding → Similarity Search → Context Retrieval → LLM Response
```

1. **Query Embedding**: Converts user's question into a vector
2. **Similarity Search**: Finds the most relevant document chunks in Pinecone
3. **Context Augmentation**: Combines retrieved context with the user's query
4. **LLM Generation**: Uses Gemini AI to generate an answer based on the context
5. **Agent Execution**: Intelligently decides when to use the retrieval tool vs. general knowledge

## ✨ Features

- **Multi-format Support**: Ingests PDF and Markdown documents
- **Intelligent Agent**: Uses LangChain agents to decide when to retrieve personal information
- **Conversation History**: Maintains context across multiple turns
- **Source Attribution**: Tracks which documents were used to answer questions
- **Flexible Model Support**: Compatible with both Google Gemini and OpenAI models
- **Error Handling**: Graceful handling of parsing errors and edge cases
- **Configurable**: Easy configuration through `config.py`

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    RAGChatbot (rag.py)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          LangChain Agent Executor                     │  │
│  │  • Manages conversation flow                          │  │
│  │  • Decides when to use tools                          │  │
│  │  • Maintains chat history                             │  │
│  └─────────────────────┬─────────────────────────────────┘  │
└────────────────────────┼────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  Should use retrieval tool?   │
         └───────┬───────────────┬───────┘
                 │               │
            Yes  │               │  No
                 ▼               ▼
    ┌────────────────────┐  ┌──────────────────┐
    │ retrieve_personal_ │  │  Direct LLM      │
    │ info (tools.py)    │  │  Response        │
    └─────────┬──────────┘  └──────────────────┘
              │
              ▼
    ┌────────────────────┐
    │ Pinecone Vector DB │
    │ • Similarity search│
    │ • Top-K retrieval  │
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │ Retrieved Context  │
    │ + Sources          │
    └─────────┬──────────┘
              │
              ▼
    ┌────────────────────┐
    │   Gemini/OpenAI    │
    │   Final Answer     │
    └────────────────────┘
```

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd RAG_chatbot
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   venv\Scripts\activate  
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment file**
   Create a `.env` file in the project root:
   ```env
   PINECONE_API_KEY=your_pinecone_api_key
   GEMINI_API_KEY=your_gemini_api_key
   # Optional: if using OpenAI
   # OPENAI_API_KEY=your_openai_api_key
   ```

## ⚙️ Configuration

Edit `config.py` to customize the chatbot:

```python
# Personal Information
NAME = "YourName"              # Person the chatbot represents
CHAT_BOT_NAME = "AssistantName" # Chatbot's name

# Pinecone Configuration
PINECONE_INDEX_NAME = "your-index-name"
PINECONE_TOP_K = 5  # Number of documents to retrieve

# Model Configuration
CHAT_MODEL_PROVIDER = 'gemini'  # or 'openai'
CHAT_MODEL_NAME = 'gemini-2.5-pro'
EMBEDDING_MODEL_NAME = "models/embedding-001"
```

## 📖 Usage

### Step 1: Ingest Your Documents

Place your PDF and Markdown files in a folder, then run:

```bash
python ingest.py --data_path "path\to\your\documents"
```

This will:
- Load all PDF and MD files from the specified folder
- Split them into chunks
- Generate embeddings
- Store them in your Pinecone index

### Step 2: Run the Chatbot

```bash
python main.py
```

Then start chatting! Examples:

```
You: What projects has Praneeth worked on?
Viva: According to the documents, Praneeth has worked on...

You: What are his technical skills?
Viva: Based on his resume, his technical skills include...

You: What's the weather like today?
Viva: I don't have access to real-time weather information, but...
```

Type `exit`, `quit`, or `bye` to end the conversation.

## 🔧 Technical Details

### Document Processing

- **Supported Formats**: PDF (via PyPDFLoader), Markdown (via UnstructuredMarkdownLoader)
- **Chunking Strategy**: RecursiveCharacterTextSplitter
  - Chunk size: 1000 characters
  - Chunk overlap: 200 characters (preserves context across chunks)

### Embedding Model

- **Provider**: Google Generative AI
- **Model**: `models/embedding-001`
- **Task Type**: `RETRIEVAL_QUERY` (optimized for search)

### Chat Model

- **Provider**: Google Gemini (configurable to OpenAI)
- **Model**: `gemini-2.5-pro`
- **Temperature**: 0.7 (balanced creativity and accuracy)

### Vector Store

- **Provider**: Pinecone
- **Similarity Metric**: Cosine similarity (default)
- **Top-K Retrieval**: 5 most relevant chunks per query

### Agent Framework

- **Framework**: LangChain
- **Agent Type**: Tool-calling agent
- **Tools**: Custom `retrieve_personal_info` tool
- **Memory**: Conversation history with `MessagesPlaceholder`

### Prompt Engineering

The system uses a carefully crafted prompt that:
- Instructs the agent when to use retrieval vs. general knowledge
- Ensures responses are grounded in retrieved context
- Prevents hallucination by enforcing source-based answers
- Maintains a professional and helpful tone

