# Viva - Personal AI Assistant

A comprehensive microservices-based chatbot application that uses RAG (Retrieval-Augmented Generation) to answer questions about personal documents and information. The chatbot can retrieve information from uploaded documents stored in a vector database and provide intelligent, context-aware responses.

## 🌟 Key Features

- **Intelligent RAG System**: Retrieve and answer questions based on personal documents using vector similarity search
- **Multi-Service Architecture**: Modular microservices design for scalability and maintainability
- **User Authentication**: Secure JWT-based authentication and user management
- **Chat History**: Persistent chat sessions with conversation summarization
- **Document Management**: Upload and process various document formats (PDF, DOCX, TXT, etc.)
- **Real-time Caching**: Redis-based caching for improved performance
- **Modern UI**: React-based responsive user interface with TypeScript

## 🏗️ System Architecture

### Service Interconnection Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                Frontend (React + TypeScript)                    │
│                    - User Interface                             │
│                    - State Management (Redux)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTP/REST API
                            │
┌───────────────────────────┴────────────────────────────────────┐
│                     API Gateway Layer                          │
│                    (JWT Token Validation)                      │
└─────┬──────────┬─────────┬──────────┬────────────┬─────────────┘
      │          │         │          │            │
      │          │         │          │            │
┌─────▼─────┐ ┌──▼────┐ ┌─▼─────┐ ┌──▼──────┐ ┌───▼────────┐
│   User    │ │  RAG  │ │ Chat  │ │  Cache  │ │ VectorStore│
│  Service  │ │Service│ │Service│ │ Service │ │  Service   │
└─────┬─────┘ └───┬───┘ └───┬───┘ └────┬────┘ └─────┬──────┘
      │           │         │          │            │
      │           │         │          │            │
┌─────▼─────┐ ┌───▼──────────▼─────┐ ┌─▼──────┐ ┌──▼───────┐
│PostgreSQL │ │  Service Mesh      │ │ Redis  │ │ Pinecone │
│(User Data)│ │  (Inter-service    │ │(Cache) │ │(Vectors) │
└───────────┘ │   Communication)   │ └────────┘ └──────────┘
              └───────┬────────────┘
                      │
              ┌───────▼────────┐
              │   Cassandra    │
              │ (Chat History) │
              └────────────────┘

Data Flow:
1. User → Frontend → User Service → PostgreSQL (Authentication)
2. Frontend → RAG Service → VectorStore → Pinecone (Document Search)
3. RAG Service → Chat Service → Cassandra (Conversation History)
4. RAG Service → Cache Service → Redis (Session Caching)
5. RAG Service → LLM (Gemini/OpenAI) → Response Generation
```

## 📋 Services Overview

### 1. **User Service**
- **Purpose**: Manages user authentication and authorization
- **Database**: PostgreSQL
- **Key Functions**:
  - User registration and login
  - JWT token generation and validation
  - Password hashing and security
  - User profile management
- **API Port**: 8001

### 2. **RAG Service** (Orchestrator)
- **Purpose**: Central orchestrator that coordinates all services to provide intelligent responses
- **Key Functions**:
  - Receives user queries and determines if document retrieval is needed
  - Coordinates with VectorStore for document retrieval
  - Integrates with Chat Service for conversation management
  - Uses LLM (Gemini/OpenAI) with agentic tools for response generation
  - Manages conversation summarization
  - Implements retry logic and error handling
- **API Port**: 8004
- **Dependencies**: All other services

### 3. **Chat Service**
- **Purpose**: Manages chat sessions and conversation history
- **Database**: Apache Cassandra
- **Key Functions**:
  - Create and manage chat sessions
  - Store conversation messages with timestamps
  - Retrieve chat history
  - Support for conversation summarization
  - Efficient time-series data storage
- **API Port**: 8002

### 4. **Cache Service**
- **Purpose**: Provides high-performance caching layer
- **Database**: Redis
- **Key Functions**:
  - Cache chat messages for quick retrieval
  - Write-through caching strategy
  - TTL-based cache invalidation
  - Reduce database load
  - Session management
- **API Port**: 8003

### 5. **VectorStore Service**
- **Purpose**: Manages document storage and vector similarity search
- **Database**: Pinecone (Vector Database)
- **Key Functions**:
  - Upload and process documents (PDF, DOCX, TXT, etc.)
  - Generate embeddings using LLM models
  - Store documents in S3 (optional)
  - Perform semantic search on documents
  - Return relevant context with similarity scores
  - Support for multiple document formats
- **API Port**: 8005

### 6. **Frontend (UI)**
- **Technology**: React + TypeScript + Redux + TailwindCSS
- **Key Functions**:
  - User authentication interface
  - Real-time chat interface
  - Session management
  - Document upload interface
  - Responsive design
- **Dev Port**: 5173

## 🔄 Request Flow Example

### Example: User asks "What are my skills?"

```
1. User types query in Frontend
   └─> POST /api/rag/chat

2. RAG Service receives request
   ├─> Validates JWT token (User Service)
   ├─> Determines query needs document retrieval
   └─> Creates/retrieves chat session (Chat Service)

3. Document Retrieval Flow
   └─> RAG Service → VectorStore Service
       ├─> Generate query embedding
       ├─> Search Pinecone for similar documents
       └─> Return relevant context with sources

4. Response Generation
   └─> RAG Service → LLM (Gemini/OpenAI)
       ├─> Provide system prompt with context
       ├─> Include conversation history
       └─> Generate contextual response

5. Storage & Caching
   ├─> Store message in Cassandra (Chat Service)
   └─> Cache in Redis (Cache Service)

6. Response Stream
   └─> RAG Service → Frontend
```

## Video Demo

[Video](https://drive.google.com/file/d/1WAhNzH7e4Uan9a6GcSvUkzviqqqHBXkC/view)

## 🚀 Getting Started

### Installation

#### 1. Clone the repository

```bash
git clone <repository-url>
cd Learning_chatbot
```

#### 2. Set up environment variables

Create a `.env` file in the root directory:

```bash
# PostgreSQL Configuration
POSTGRES_DB=chatbot_users
POSTGRES_USERNAME=your_user_name
POSTGRES_PASSWORD=your_password

# JWT Secret
JWT_SECRET=your_secret_key_here

# LLM API Keys
GOOGLE_API_KEY=your_google_api_key
# or
OPENAI_API_KEY=your_openai_api_key

# Pinecone Configuration
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_index_name

# AWS S3 (Optional - for document storage)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your_bucket_name
AWS_REGION=us-east-1

# Service URLs (for inter-service communication)
USER_SERVICE_URL=http://localhost:8001
CHAT_SERVICE_URL=http://localhost:8002
CACHE_SERVICE_URL=http://localhost:8003
RAG_SERVICE_URL=http://localhost:8004
VECTORSTORE_SERVICE_URL=http://localhost:8005
```

Copy the `.env` file to each service directory:

```bash
cp .env User/.env
cp .env Chat/.env
cp .env Cache/.env
cp .env RAG/.env
cp .env VectorStore/.env
```

#### 3. Set up databases

**PostgreSQL:**
```bash
./setup_postgres.sh
```

#### 4. Install Python dependencies

```bash
# Install dependencies for all services
pip install -r requirements.txt

# Or install individually
pip install -r User/requirements.txt
pip install -r Chat/requirements.txt
pip install -r Cache/requirements.txt
pip install -r RAG/requirements.txt
pip install -r VectorStore/requirements.txt
```

#### 5. Set up Frontend

```bash
cd UI
npm install
```

### Running the Application

#### Start all services using the helper script

```bash
./start_services.sh
```

#### Frontend:

```bash
# Terminal 6 - Frontend
cd UI && npm run dev
```

Access the application at: `http://localhost:3000`

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run specific service tests
pytest tests/User/
pytest tests/Chat/
pytest tests/Cache/
pytest tests/RAG/
pytest tests/VectorStore/
```

## 📚 Usage

### 1. Register/Login
- Navigate to the login page
- Create a new account or login with existing credentials

### 2. Upload Documents
- Use the document upload interface
- Supported formats: PDF, DOCX, TXT, MD
- Documents are processed and embedded into the vector store

### 3. Chat with Your Data
- Start asking questions about your documents
- The chatbot will retrieve relevant context and provide intelligent answers
- View conversation history and create multiple chat sessions

### 4. Conversation Features
- **Context-Aware**: Maintains conversation context
- **Source Citations**: References source documents in responses
- **Summarization**: Automatic conversation summarization

## 🛠️ Configuration

Each service has its own `config.yaml` file for customization:

- **User/config.yaml**: PostgreSQL connection, JWT settings
- **Chat/config.yaml**: Cassandra connection settings
- **Cache/config.yaml**: Redis connection settings
- **RAG/config.yaml**: LLM models, prompts, retry settings
- **VectorStore/config.yaml**: Embedding models, chunk settings

## 📖 API Documentation

Each service has comprehensive API documentation:

- User Service: [USER_SERVICE_API.md](User/USER_SERVICE_API.md)
- Chat Service: [CHAT_SERVICE_API.md](Chat/CHAT_SERVICE_API.md)
- Cache Service: [CACHE_SERVICE_API.md](Cache/CACHE_SERVICE_API.md)
- RAG Service: [RAG_SERVICE_API.md](RAG/RAG_SERVICE_API.md)
- VectorStore Service: [VECTORSTORE_SERVICE_API.md](VectorStore/VECTORSTORE_SERVICE_API.md)

## 🔒 Security

- **JWT Authentication**: All endpoints (except auth) require valid JWT tokens
- **Password Hashing**: Secure password storage using industry-standard hashing
- **Token Refresh**: Automatic token refresh mechanism
- **Environment Variables**: Sensitive data stored in environment variables
- **CORS Configuration**: Proper CORS settings for production


## Future Improvements
- Streaming responses for better UI
- Docker support for each micro-service.
- CI/CD workflow
- GCP deployment.