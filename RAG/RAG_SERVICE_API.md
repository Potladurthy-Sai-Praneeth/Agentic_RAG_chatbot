# RAG Service API Documentation

## Overview

The RAG Service API is a FastAPI-based microservice that orchestrates Retrieval-Augmented Generation (RAG) functionality. It acts as the main orchestration layer that integrates with Cache, Chat, VectorStore, and User services to provide intelligent conversational AI capabilities with context-aware responses based on personal documents.

**Base URL**: `http://localhost:8005`  
**Version**: 1.0.0

---

## Authentication

All endpoints (except `/health` and `/`) require JWT Bearer token authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

The token should be obtained from the User Service `/login` endpoint. The token payload must contain:
- `sub`: User ID
- `type`: "access"

---

## Endpoints

### 1. Chat with Agent

**Endpoint**: `POST /rag/{session_id}/chat`

**Description**: Send a user message and receive an AI-generated response. This endpoint stores the user message, invokes the RAG agent with context from previous conversations and relevant documents, stores the assistant's response, and optionally sets the session title for the first message.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Request Body**:
```json
{
  "role": "user",
  "content": "string",
  "is_first_message": false
}
```

**Request Model**: `UserMessageRequestModel`
- `role` (string, required): The role of the message sender (typically "user")
- `content` (string, required): The user's message content
- `is_first_message` (boolean, optional): Set to `true` if this is the first message in the session to automatically generate a session title. Defaults to `false`.

**Response**: `201 Created`

**Response Model**: `AssistantMessageResponseModel`
```json
{
  "message_id": "string",
  "timestamp": "datetime",
  "success": true,
  "response": "string"
}
```

**Response Fields**:
- `message_id` (string): Unique TimeUUID identifier for the assistant's response message
- `timestamp` (datetime): Timestamp when the response was generated
- `success` (boolean): Indicates if the operation was successful
- `response` (string): The AI assistant's response text

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to process chat request

**Notes**:
- Message IDs are generated as TimeUUIDs (v1) for Cassandra compatibility
- The agent uses context from cached messages, session summaries, and document retrieval
- For the first message, set `is_first_message: true` to auto-generate a session title
- Both user and assistant messages are automatically stored in Chat and Cache services

---

### 2. Get Session Messages

**Endpoint**: `GET /rag/{session_id}/get-session-messages`

**Description**: Retrieve all chat messages for a specific session. This endpoint automatically restores session summaries from the database to cache if needed.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Response**: `200 OK`

**Response Model**: `List[GetChatMessagesResponseModel]`
```json
[
  {
    "message_id": "string",
    "role": "string",
    "content": "string",
    "timestamp": "datetime"
  }
]
```

**Response Fields** (per message):
- `message_id` (string): Unique identifier for the message
- `role` (string): The role of the message sender (e.g., "user", "assistant", "system")
- `content` (string): The message content
- `timestamp` (datetime): Timestamp when the message was created

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to retrieve messages

**Notes**:
- Returns messages from the persistent database (Chat Service)
- Automatically restores session summaries to cache if the session is not found in cache
- Returns an empty array if no messages exist for the session

---

### 3. Get User Sessions

**Endpoint**: `GET /rag/get-sessions`

**Description**: Retrieve all chat sessions for the currently authenticated user.

**Authentication**: Required (Bearer Token)

**Response**: `200 OK`

**Response Model**: `List[GetAllUserSessionsResponseModel]`
```json
[
  {
    "session_id": "string",
    "created_at": "datetime",
    "title": "string (optional)"
  }
]
```

**Response Fields** (per session):
- `session_id` (string): Unique identifier for the session
- `created_at` (datetime): Timestamp when the session was created
- `title` (string, optional): Human-readable title for the session

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to retrieve sessions

**Notes**:
- Returns all sessions for the authenticated user from the User Service
- Sessions are ordered by creation date
- Empty sessions (without messages) are included in the response

---

### 4. Create New Session

**Endpoint**: `POST /rag/create-session`

**Description**: Create a new chat session for the currently authenticated user.

**Authentication**: Required (Bearer Token)

**Response**: `201 Created`

**Response Model**: `CreateNewSessionResponseModel`
```json
{
  "session_id": "string",
  "created_at": "datetime"
}
```

**Response Fields**:
- `session_id` (string): Unique UUID identifier for the newly created session
- `created_at` (datetime): Timestamp when the session was created

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to create session

**Notes**:
- Session ID is generated as a UUID v4
- Sessions are created in the User Service
- A new session starts with no messages or cache data

---

### 5. Delete Session

**Endpoint**: `DELETE /rag/{session_id}/delete-session`

**Description**: Delete a session and all associated data including messages, cache, and session metadata.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session to delete

**Response**: `200 OK`

**Response Model**: `DeleteSessionResponseModel`
```json
{
  "success": true,
  "message": "string"
}
```

**Response Fields**:
- `success` (boolean): Indicates if the deletion was successful
- `message` (string): Confirmation message about the deletion

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to delete session

**Notes**:
- Deletes data from Cache Service (cached messages and summaries)
- Deletes data from Chat Service (persistent messages)
- Deletes session metadata from User Service
- This operation is irreversible
- Deletion proceeds even if some services fail (best-effort deletion)

---

### 6. Clear All User Caches

**Endpoint**: `DELETE /rag/clear-all-caches`

**Description**: Clear all cached data (messages and summaries) for all sessions belonging to the currently authenticated user. This endpoint is typically called when a user logs out to free up Redis memory.

**Authentication**: Required (Bearer Token)

**Response**: `200 OK`

**Response Model**:
```json
{
  "success": true,
  "message": "Cleared N out of M session caches",
  "cleared_count": 5,
  "total_sessions": 5,
  "failed_sessions": []
}
```

**Response Fields**:
- `success` (boolean): Indicates if the operation completed (always true)
- `message` (string): Summary message about the cache clearing operation
- `cleared_count` (integer): Number of session caches successfully cleared
- `total_sessions` (integer): Total number of sessions the user has
- `failed_sessions` (array): List of session IDs that failed to clear (empty if all succeeded)

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Failed to retrieve sessions or clear caches

**Notes**:
- Retrieves all sessions for the user from the User Service
- Clears cache for each session individually in the Cache Service
- Does not delete sessions or persistent data - only clears Redis cache
- Best-effort operation - continues even if some sessions fail to clear
- Particularly useful on logout to save Redis memory
- Does not affect persistent data in Chat Service or session metadata in User Service

---

### 7. Health Check

**Endpoint**: `GET /health`

**Description**: Check the health status of the RAG Service and all dependent services (Cache, Chat, VectorStore, and User services).

**Authentication**: Not required

**Response**: `200 OK`

**Response Model**: `List[HealthCheckResponseModel]`
```json
[
  {
    "status": "healthy",
    "message": "Service is healthy"
  }
]
```

**Response Fields** (per service):
- `status` (string): Health status ("healthy" or "unhealthy")
- `message` (string): Detailed health check message

**Error Responses**:
- `503 Service Unavailable`: RAG service not initialized
- `500 Internal Server Error`: Health check failed

**Notes**:
- Checks connectivity to all dependent services
- Returns health status for each service individually
- A delay is added before checking VectorStore service to allow for initialization

---

### 8. Root Endpoint

**Endpoint**: `GET /`

**Description**: Welcome endpoint that provides service information and available endpoints.

**Authentication**: Not required

**Response**: `200 OK`

**Response**:
```json
{
  "service": "RAG Service API",
  "status": "running",
  "message": "Welcome to the RAG Service API!",
  "endpoints": {
    "GET /rag/{session_id}/get-session-messages": "Retrieve chat messages for a session",
    "POST /rag/{session_id}/chat": "Invoke the agent to respond to the user query",
    "GET /rag/get-sessions": "Retrieve all session IDs for the current user",
    "POST /rag/create-session": "Create a new session for the current user",
    "DELETE /rag/{session_id}/delete-session": "Delete the session and all associated messages",
    "DELETE /rag/clear-all-caches": "Clear all cached sessions for the current user (on logout)",
    "GET /health": "Health check endpoint for RAG service"
  }
}
```

---

## Data Types

### Common Types

- **string**: Text data
- **datetime**: ISO 8601 formatted datetime string (e.g., "2024-01-15T10:30:00")
- **boolean**: true or false
- **UUID**: Universally unique identifier (string format)
- **TimeUUID**: Time-based UUID (v1) for Cassandra compatibility

### Role Values

The `role` field in messages typically accepts:
- `"user"`: Messages from the user
- `"assistant"`: Messages from the AI assistant
- `"system"`: System messages

---

## Service Architecture

The RAG Service orchestrates multiple backend services:

### Dependent Services

1. **Cache Service** (`http://localhost:8003`): Fast Redis-based message caching and session summaries
2. **Chat Service** (`http://localhost:8002`): Persistent message storage in Cassandra
3. **VectorStore Service** (`http://localhost:8004`): Document retrieval and vector search
4. **User Service** (`http://localhost:8001`): User authentication and session management

### Data Flow

1. **User Message**: Stored in both Chat Service (persistent) and Cache Service (fast access)
2. **Context Retrieval**: Agent retrieves context from Cache (recent messages + summary) and VectorStore (relevant documents)
3. **AI Response**: Generated using LangChain agent with retrieved context
4. **Summarization**: Triggered automatically when message count exceeds configured limit
5. **Response Storage**: Assistant message stored in both Chat and Cache services

---

## Configuration

The RAG Service uses a `config.yaml` file and environment variables for configuration:

### Environment Variables (Required)

```bash
CACHE_SERVICE_URL=http://localhost:8003
CHAT_SERVICE_URL=http://localhost:8002
VECTORSTORE_SERVICE_URL=http://localhost:8004
USER_SERVICE_URL=http://localhost:8001
GOOGLE_API_KEY=your_google_api_key  # If using Gemini models
OPENAI_API_KEY=your_openai_api_key  # If using OpenAI models
```

### Configuration File (`config.yaml`)

```yaml
# Model Configuration
models:
  summary:
    provider: "gemini"  # or "openai"
    name: "gemini-2.5-flash"
  
  chat:
    provider: "gemini"  # or "openai"
    name: "gemini-2.5-pro"
  
  embedding:
    provider: "gemini"
    name: "models/embedding-001"
    task_type: "RETRIEVAL_QUERY"

# User Configuration
user:
  name: "User Name"
  chatbot_name: "Assistant Name"

# Retry Configuration
retry:
  service_timeout: 30
  stream_timeout: 60
  max_retries: 3
  retry_delay: 1.0
  enable_streaming: true

# Vector Database Configuration
pinecone:
  top_k: 10
  min_similarity_score: 0.3
```

---

## Integration Notes

### For Frontend/Client Applications

1. **Authentication Flow**:
   - Obtain JWT access token from User Service `/login` endpoint
   - Include token in `Authorization: Bearer <token>` header for all authenticated requests

2. **Session Management**:
   - Create a new session with `POST /rag/create-session` before starting a conversation
   - Use the returned `session_id` for all subsequent chat operations
   - Mark the first message with `is_first_message: true` to auto-generate session title
   - List all sessions with `GET /rag/get-sessions`
   - Delete sessions with `DELETE /rag/{session_id}/delete-session`

3. **Chat Flow**:
   - Send user messages via `POST /rag/{session_id}/chat`
   - Retrieve conversation history with `GET /rag/{session_id}/get-session-messages`
   - The agent automatically uses context from previous messages and relevant documents

4. **Logout Flow**:
   - Call `DELETE /rag/clear-all-caches` to clear all Redis caches for the user
   - This frees up Redis memory while preserving persistent data
   - Then proceed with normal logout (clear local tokens)

5. **Error Handling**:
   - `401 Unauthorized`: Token expired or invalid - re-authenticate
   - `503 Service Unavailable`: Service starting up - retry after delay
   - `500 Internal Server Error`: Log error and retry with exponential backoff

6. **CORS**: The service allows CORS from all origins. Configure appropriately for production.

---

## Example Usage

### Create a New Session

```bash
curl -X POST "http://localhost:8005/rag/create-session" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00"
}
```

### Send a Chat Message

```bash
curl -X POST "http://localhost:8005/rag/550e8400-e29b-41d4-a716-446655440000/chat" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "What projects has Praneeth worked on?",
    "is_first_message": true
  }'
```

**Response**:
```json
{
  "message_id": "c2c14bb0-b3d4-11eb-8529-0242ac130003",
  "timestamp": "2024-01-15T10:30:15",
  "success": true,
  "response": "Based on Praneeth's documents, he has worked on several projects including..."
}
```

### Get Session Messages

```bash
curl -X GET "http://localhost:8005/rag/550e8400-e29b-41d4-a716-446655440000/get-session-messages" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
[
  {
    "message_id": "c2c14bb0-b3d4-11eb-8529-0242ac130002",
    "role": "user",
    "content": "What projects has Praneeth worked on?",
    "timestamp": "2024-01-15T10:30:10"
  },
  {
    "message_id": "c2c14bb0-b3d4-11eb-8529-0242ac130003",
    "role": "assistant",
    "content": "Based on Praneeth's documents, he has worked on several projects including...",
    "timestamp": "2024-01-15T10:30:15"
  }
]
```

### Get All Sessions

```bash
curl -X GET "http://localhost:8005/rag/get-sessions" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
[
  {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2024-01-15T10:30:00",
    "title": "Projects Discussion"
  },
  {
    "session_id": "660e8400-e29b-41d4-a716-446655440001",
    "created_at": "2024-01-14T09:15:00",
    "title": "Skills and Experience"
  }
]
```

### Delete a Session

```bash
curl -X DELETE "http://localhost:8005/rag/550e8400-e29b-41d4-a716-446655440000/delete-session" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "success": true,
  "message": "Session 550e8400-e29b-41d4-a716-446655440000 deletion process completed."
}
```

### Clear All User Caches (On Logout)

```bash
curl -X DELETE "http://localhost:8005/rag/clear-all-caches" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "success": true,
  "message": "Cleared 5 out of 5 session caches",
  "cleared_count": 5,
  "total_sessions": 5,
  "failed_sessions": []
}
```

### Health Check

```bash
curl -X GET "http://localhost:8005/health"
```

**Response**:
```json
[
  {
    "status": "healthy",
    "message": "Service is healthy"
  },
  {
    "status": "healthy",
    "message": "Service is healthy"
  },
  {
    "status": "healthy",
    "message": "Service is healthy"
  },
  {
    "status": "healthy",
    "message": "Service is healthy"
  }
]
```

---

## RAG Agent Capabilities

The RAG agent is powered by LangChain and has access to specialized tools:

### Document Retrieval Tool

- **Tool Name**: `retrieve_personal_info`
- **Purpose**: Search through personal documents for relevant information
- **Usage**: Automatically invoked when questions relate to the document owner's background, experience, projects, skills, or qualifications
- **Returns**: Context and sources from relevant documents

### Agent Behavior

1. **Context-Aware**: Uses conversation history and session summaries for continuity
2. **Document-Grounded**: Retrieves and cites information from personal documents
3. **Summarization**: Automatically creates and updates conversation summaries to maintain context in long conversations
4. **Source Attribution**: Can reference document sources when providing information

---

## Performance Considerations

1. **Caching Strategy**: 
   - Recent messages cached in Redis for fast access
   - Summaries maintained to reduce context size
   - Automatic cache trimming after summarization

2. **LLM Configuration**:
   - Separate models for chat (higher quality) and summarization (faster)
   - Temperature set to 0.5 for balanced creativity and consistency

3. **Vector Search**:
   - Configurable `top_k` for number of document chunks retrieved
   - Minimum similarity threshold to filter irrelevant results

4. **Service Timeouts**:
   - Configurable timeouts for service requests
   - Automatic retry logic with exponential backoff

---

## Security Considerations

1. **Authentication**: All endpoints (except `/health` and `/`) require valid JWT tokens
2. **Session Isolation**: Users can only access their own sessions - validated via JWT token
3. **Service Communication**: Internal service calls authenticated with JWT token forwarding
4. **Data Privacy**: Documents and conversations are user-specific and isolated
5. **API Keys**: Model API keys (Google/OpenAI) stored securely in environment variables

---

## Error Scenarios

### Service Unavailable

If dependent services are unavailable:
- Health check will return degraded status for affected services
- RAG operations may fail if required services are down
- Service will attempt automatic reconnection

### Model API Errors

If LLM API calls fail:
- Error logged with details
- HTTP 500 returned to client
- Retry logic applied based on configuration

### Cache Miss with Restoration

If cache is empty but database has data:
- Messages retrieved from Chat Service
- Summary automatically restored to cache
- Transparent to the client

---

## Typical Workflow

### New Conversation

1. **Create Session**: `POST /rag/create-session`
2. **First Message**: `POST /rag/{session_id}/chat` with `is_first_message: true`
3. **Continue Chat**: `POST /rag/{session_id}/chat` for subsequent messages
4. **View History**: `GET /rag/{session_id}/get-session-messages` anytime

### Resuming a Conversation

1. **List Sessions**: `GET /rag/get-sessions`
2. **Load Messages**: `GET /rag/{session_id}/get-session-messages`
3. **Continue Chat**: `POST /rag/{session_id}/chat`

### Cleanup

1. **Delete Session**: `DELETE /rag/{session_id}/delete-session`
2. **Clear All Data**: Removes from cache, database, and session metadata

### Logout Cleanup

1. **Clear All Caches**: `DELETE /rag/clear-all-caches`
2. **Free Redis Memory**: Clears cached messages and summaries for all user sessions
3. **Preserve Data**: Persistent data in database remains intact

---

## Development and Testing

### Running the Service

```bash
# Set environment variables
export CACHE_SERVICE_URL=http://localhost:8003
export CHAT_SERVICE_URL=http://localhost:8002
export VECTORSTORE_SERVICE_URL=http://localhost:8004
export USER_SERVICE_URL=http://localhost:8001
export GOOGLE_API_KEY=your_api_key

# Run the service
python -m RAG.rag_api
# or
uvicorn RAG.rag_api:app --host 0.0.0.0 --port 8005 --reload
```

### API Documentation

- **Interactive Docs**: `http://localhost:8005/docs` (Swagger UI)
- **OpenAPI Spec**: `http://localhost:8005/openapi.json`
- **ReDoc**: `http://localhost:8005/redoc`

---

## Troubleshooting

### Common Issues

1. **Service Not Initialized Error**:
   - Check that all environment variables are set correctly
   - Verify dependent services are running and healthy
   - Check logs for initialization errors

2. **Authentication Failures**:
   - Verify JWT token is valid and not expired
   - Ensure token includes required fields (`sub`, `type`)
   - Check that User Service is accessible

3. **Empty or Missing Context**:
   - Verify VectorStore service is running and has documents indexed
   - Check that search parameters in config.yaml are appropriate
   - Ensure document embeddings are generated

4. **Slow Responses**:
   - Check LLM API rate limits and quotas
   - Verify network connectivity to model providers
   - Review timeout configurations
   - Consider using faster models for summarization

---

This documentation reflects the current implementation of the RAG Service API. For updates or specific implementation details, refer to the source code and configuration files.
