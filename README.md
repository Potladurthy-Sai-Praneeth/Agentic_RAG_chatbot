# RAG Chatbot - Personal Information Assistant

A sophisticated Retrieval-Augmented Generation (RAG) chatbot that answers questions about personal documents, resumes, projects, and professional information. Built with LangChain, Pinecone, Google's Gemini AI, and a robust database architecture using Cassandra and Redis for session management and conversation history.

## 🤖 What is RAG?

**Retrieval-Augmented Generation (RAG)** is an AI framework that enhances Large Language Models (LLMs) by combining them with external knowledge retrieval. Instead of relying solely on the model's training data, RAG:

1. **Retrieves** relevant information from a knowledge base (vector database)
2. **Augments** the user's query with this retrieved context
3. **Generates** accurate, contextual responses based on the retrieved information


## 🔄 How This Project Works

This RAG chatbot follows a multi-phase workflow with integrated database management:

### Phase 1: Data Ingestion (One-time Setup)
```
Documents (PDF/MD) → Chunking → Embeddings → Vector Store (Pinecone)
```

1. **Document Loading**: Reads PDF and Markdown files from a specified folder
2. **Text Splitting**: Breaks documents into manageable chunks (1000 chars with 200 overlap)
3. **Embedding Generation**: Converts text chunks into vector representations using Google's embedding model
4. **Vector Storage**: Stores embeddings in Pinecone for fast similarity search

### Phase 2: Session Initialization
```
User Login → Generate Session ID → Initialize Database Tables
```

1. **Session Creation**: Creates unique session ID for each conversation
2. **Database Setup**: Ensures Cassandra keyspace and tables exist
3. **Cache Initialization**: Connects to Redis for message caching
4. **User Tracking**: Associates session with user_id

### Phase 3: Query Answering (Runtime)
```
User Query → Cache → Database → Embedding → Similarity Search → LLM Response → Store
```

1. **Query Input**: Receives user's question
2. **Context Retrieval**: Fetches recent messages from Redis cache + summaries from Cassandra
3. **Query Embedding**: Converts user's question into a vector (if retrieval needed)
4. **Similarity Search**: Finds the most relevant document chunks in Pinecone
5. **Context Augmentation**: Combines conversation history + retrieved context + user's query
6. **LLM Generation**: Uses Gemini AI to generate an answer based on the context
7. **Storage**: Writes user message and bot response to both Redis (cache) and Cassandra (persistent)
8. **Summarization Check**: If cache limit reached, trigger summarization and clear cache

### Phase 4: Conversation Summarization (Automatic)
```
Cache Limit Reached → Retrieve Messages → Summarize → Store Summary → Clear Cache
```

1. **Trigger**: Activated when message count reaches `CACHE_MESSAGE_LIMIT`
2. **Message Retrieval**: Fetches messages from cache
3. **Summarization**: Uses a fast model (gemini-flash) to create concise summary
4. **Storage**: Saves summary to Cassandra for future context
5. **Cache Reset**: Clears Redis cache to make room for new messages
6. **Context Continuity**: Summary used in future conversations to maintain context

## ✨ Features

- **Multi-format Support**: Ingests PDF and Markdown documents
- **Intelligent Agent**: Uses LangChain agents to decide when to retrieve personal information
- **Database-Backed Sessions**: 
  - **Cassandra**: Persistent storage for chat messages and conversation summaries
  - **Redis**: High-performance caching layer for recent messages
- **Smart Conversation Management**: 
  - Automatic summarization of conversation history when cache limit is reached
  - Write-through caching strategy for optimal performance
  - Session-based tracking with unique session IDs per user
- **Conversation History**: Maintains context across multiple turns with persistent storage
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
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌──────────────────┐          ┌─────────────────────┐
│  Session Manager │          │  Should use         │
│  (session_mgr)   │          │  retrieval tool?    │
│  • User sessions │          └──────┬──────────────┘
│  • Session IDs   │                 │       |
└────────┬─────────┘            Yes  │     No|
         │                           │       │
         ▼                           ▼       ▼
┌──────────────────────────────────────┐  ┌──────────┐
│    Database Layer (db_manager.py)    │  │ Direct   │
│  ┌──────────────┐  ┌──────────────┐  │  │ LLM      │
│  │  Cassandra   │  │    Redis     │  │  │ Response │
│  │  (Persistent)│  │   (Cache)    │  │  └──────────┘
│  │              │  │              │  │
│  │ • Messages   │  │ • Recent k   │  │
│  │ • Summaries  │  │   messages   │  │
│  │ • Metadata   │  │ • Fast read  │  │
│  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Summarization Service│
│ • Triggered at limit │
│ • Stores in Cassandra│
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ retrieve_personal_   │
│ info (tools.py)      │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Pinecone Vector DB   │
│ • Similarity search  │
│ • Top-K retrieval    │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│ Retrieved Context    │
│ + Sources            │
└─────────┬────────────┘
          │
          ▼
┌──────────────────────┐
│   Gemini/OpenAI      │
│   Final Answer       │
└──────────────────────┘
```

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Potladurthy-Sai-Praneeth/Agentic_RAG_chatbot.git
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
   
   This installs all required packages including:
   - LangChain and LangChain-Google-GenAI for RAG
   - Pinecone for vector storage
   - Cassandra-driver for database operations
   - Redis for caching
   - PyPDF and markdown loaders for document ingestion

4. **Set up databases**
   
   **Cassandra:**
   - Install Apache Cassandra from [cassandra.apache.org](https://cassandra.apache.org/)
   - Start Cassandra service:
     ```bash
     # Windows (if installed as service)
     net start cassandra
     
     # Or run manually from installation directory
     bin\cassandra.bat
     ```
   - Verify it's running on `localhost:9042`
   
   **Redis:**
   - Install Redis from [redis.io](https://redis.io/download) or use WSL/Docker
   - Start Redis server:
     ```bash
     redis-server
     ```
   - Verify it's running on `localhost:6379`

5. **Create environment file**
   Create a `.env` file in the project root:
   ```env
   PINECONE_API_KEY=your_pinecone_api_key
   GEMINI_API_KEY=your_gemini_api_key
   # Optional: if using OpenAI
   # OPENAI_API_KEY=your_openai_api_key
   ```

```bash
Note : Edit `config.py` to customize the chatbot:
```

### Key Components

- **`db_manager.py`**: Handles all Cassandra operations (sessions, messages, summaries)
- **`cache_manager.py`**: Manages Redis cache with write-through strategy
- **`session_manager.py`**: Creates and tracks session IDs for users
- **`summarization_service.py`**: Automatically summarizes conversations at cache limit
- **`rag.py`**: Orchestrates the RAG pipeline and agent execution
- **`tools.py`**: Implements the Pinecone retrieval tool for the agent
- **auth_manager.py**: Manages user authentication for multi-user scenarios

## �📖 Usage

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

Then start chatting! 

## 🔧 Technical Details

#### Cassandra (Persistent Storage)
- **Purpose**: Long-term storage of chat sessions, messages, and summaries
- **Schema**:
  - `chat_sessions`: Session metadata (user_id, created_at, updated_at)
  - `chat_messages`: Individual messages with timestamps
  - `chat_summaries`: Conversation summaries for context efficiency
- **Keyspace**: `chatbot_sessions` with configurable replication factor
- **Benefits**: Scalability, high availability, distributed architecture

#### Redis (Caching Layer)
- **Purpose**: High-performance caching of recent messages
- **Strategy**: Write-through caching with automatic cache invalidation
- **Cache Limit**: Configurable (default: 10 messages)
- **Workflow**:
  1. New messages written to both Redis (cache) and Cassandra (persistent)
  2. When cache reaches limit, trigger summarization
  3. Summary stored in Cassandra, cache cleared for new messages
  4. Maintains conversation context without overwhelming the LLM

#### Session Management
- **Session IDs**: UUID-based unique identifiers per user
- **User Tracking**: Separate user_id and session_id for multi-user support
- **Context Retrieval**: Combines cached messages + summaries for LLM context

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
- **Summarization Model**: `gemini-flash-latest` (faster, cost-effective)

### Vector Store

- **Provider**: Pinecone
- **Similarity Metric**: Cosine similarity (default)
- **Top-K Retrieval**: 5 most relevant chunks per query

### Agent Framework

- **Framework**: LangChain
- **Agent Type**: Tool-calling agent
- **Tools**: Custom `retrieve_personal_info` tool
- **Context Management**: Hybrid approach (recent messages + summaries)

