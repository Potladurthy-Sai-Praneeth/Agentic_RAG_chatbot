# Cache Service API Documentation

## Overview

The Cache Service API is a FastAPI-based microservice for managing Redis-based chat message caching with a write-through strategy. It provides fast access to recent chat messages and session summaries, reducing load on the primary database.

**Base URL**: `http://localhost:8003`  
**Version**: 1.0.0

---

## Authentication

Most endpoints require JWT Bearer token authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

The token should be obtained from the User Service `/login` endpoint. The token payload must contain:
- `sub`: User ID
- `type`: "access"

---

## Endpoints

### 1. Add Message to Cache

**Endpoint**: `POST /cache/{session_id}/message`

**Description**: Add a message to the Redis cache for a specific session. Returns whether summarization is needed based on the configured message limit.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Request Body**:
```json
{
  "role": "string",
  "content": "string",
  "timestamp": "datetime (optional)"
}
```

**Request Model**: `AddMessageRequestModel`
- `role` (string, required): The role of the message sender (e.g., "user", "assistant", "system")
- `content` (string, required): The message content
- `timestamp` (datetime, optional): Timestamp when the message was created. Currently stored but not used for ordering.

**Response**: `201 Created`

**Response Model**: `AddMessageResponseModel`
```json
{
  "message": "Message added successfully",
  "needs_summarization": false
}
```

**Response Fields**:
- `message` (string): Success message
- `needs_summarization` (boolean): `true` if the message limit has been reached and summarization should be triggered, `false` otherwise

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to add message to cache

**Notes**:
- Messages are stored in Redis as a list (using Redis LIST data structure)
- When the message count reaches the configured limit (default: 10), `needs_summarization` is set to `true`
- The message limit is configurable via `config.yaml` under `cache.message_limit`

---

### 2. Get Cached Messages

**Endpoint**: `GET /cache/{session_id}/messages`

**Description**: Retrieve messages from the Redis cache for a specific session. Optionally limit the number of messages returned.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Query Parameters**:
- `limit` (integer, optional): Maximum number of messages to retrieve. If not specified, all messages are returned.

**Response**: `200 OK`

**Response Model**: `List[GetCachedMessagesResponseModel]`
```json
[
  {
    "role": "string",
    "content": "string",
    "timestamp": "datetime (optional)"
  }
]
```

**Response Fields** (per message):
- `role` (string): The role of the message sender
- `content` (string): The message content
- `timestamp` (datetime, optional): Timestamp when the message was created

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to retrieve messages from cache

**Notes**:
- Messages are returned in the order they were added (oldest first)
- When `limit` is specified, returns the last N messages
- Returns an empty array if no messages exist for the session

---

### 3. Get Message Count

**Endpoint**: `GET /cache/{session_id}/message_count`

**Description**: Get the count of cached messages for a specific session.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Response**: `200 OK`

**Response Model**: `GetMessageCountResponseModel`
```json
{
  "count": 5
}
```

**Response Fields**:
- `count` (integer): Number of messages currently cached for the session

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to retrieve message count from cache

**Notes**:
- Returns `0` if no messages exist for the session
- Count reflects the actual number of messages in Redis, not a cached counter

---

### 4. Trim Cache

**Endpoint**: `DELETE /cache/{session_id}/trim`

**Description**: Trim the cache for a session to keep only the last N messages. This is useful when summarization occurs and older messages need to be removed.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Query Parameters**:
- `keep_last` (integer, optional, must be > 0): Number of messages to keep. If not specified or if current count is less than `keep_last`, no trimming occurs.

**Response**: `200 OK`

**Response Model**: `TrimCacheResponseModel`
```json
{
  "message": "Cache trimmed successfully",
  "needs_summarization": false
}
```

**Response Fields**:
- `message` (string): Success message
- `needs_summarization` (boolean): `true` if trimming occurred and summarization may be needed, `false` otherwise

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to trim cache

**Notes**:
- Only trims if the current message count exceeds `keep_last`
- Returns `needs_summarization: true` if trimming was performed
- Older messages (from the beginning of the list) are removed

---

### 5. Update Session Summary

**Endpoint**: `POST /cache/{session_id}/update-summary`

**Description**: Update or store the session summary in the Redis cache.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Request Body**:
```json
{
  "summary": "string",
  "timestamp": "datetime (optional)"
}
```

**Request Model**: `UpdateCacheSummaryRequestModel`
- `summary` (string, required): The summary text to store in the cache
- `timestamp` (datetime, optional): Timestamp when the summary was created

**Response**: `200 OK`

**Response Model**: `UpdateCacheSummaryResponseModel`
```json
{
  "message": "Session summary updated successfully",
  "success": true
}
```

**Response Fields**:
- `message` (string): Success message
- `success` (boolean): Indicates if the operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to update session summary in cache

**Notes**:
- Overwrites any existing summary for the session
- Summary is stored as a simple string value in Redis

---

### 6. Get Session Summary

**Endpoint**: `GET /cache/{session_id}/get-summary`

**Description**: Retrieve the session summary from the Redis cache.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Response**: `200 OK`

**Response Model**: `GetCacheSummaryResponseModel`
```json
{
  "summary": "string or null",
  "success": true
}
```

**Response Fields**:
- `summary` (string or null): The session summary text, or `null` if no summary exists
- `success` (boolean): Indicates if the operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to retrieve session summary from cache

**Notes**:
- Returns `null` for `summary` if no summary has been stored for the session
- Summary is retrieved from Redis cache, not from the primary database

---

### 7. Clear Cache

**Endpoint**: `DELETE /cache/{session_id}/clear`

**Description**: Clear all cached data (messages and summary) for a specific session from Redis.

**Authentication**: Required (Bearer Token)

**Path Parameters**:
- `session_id` (string, required): The unique identifier for the chat session

**Response**: `200 OK`

**Response Model**: `ClearCacheResponseModel`
```json
{
  "message": "Cache cleared successfully",
  "success": true
}
```

**Response Fields**:
- `message` (string): Success message
- `success` (boolean): Indicates if the operation was successful

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: Cache service not initialized
- `500 Internal Server Error`: Failed to clear cache

**Notes**:
- Deletes both the messages list and summary for the session
- This operation is irreversible
- Does not affect data in the primary database (Chat Service)

---

### 8. Health Check

**Endpoint**: `GET /health`

**Description**: Check the health status of the Cache Service and Redis connection.

**Authentication**: Not required

**Response**: `200 OK`

**Response Model**: `CacheHealthResponseModel`
```json
{
  "status": "healthy",
  "details": {
    "status": "Cache service is operational"
  }
}
```

**Response Fields**:
- `status` (string): Health status (e.g., "healthy")
- `details` (object, optional): Additional health check details

**Error Responses**:
- `503 Service Unavailable`: Cache service not initialized or Redis connection unavailable
- `500 Internal Server Error`: Cache service is unhealthy or health check failed

**Notes**:
- Performs a Redis PING command to verify connectivity
- Returns `503` if Redis is unreachable

---

### 9. Root Endpoint

**Endpoint**: `GET /`

**Description**: Welcome endpoint that provides service information and available endpoints.

**Authentication**: Not required

**Response**: `200 OK`

**Response**:
```json
{
  "service": "Cache Service API",
  "status": "running",
  "message": "Welcome to the Cache Service API",
  "endpoints": {
    "POST /cache/{session_id}/message": "Add a message to the cache",
    "GET /cache/{session_id}/messages": "Retrieve messages from the cache",
    "GET /cache/{session_id}/message_count": "Get cached message count for a session",
    "DELETE /cache/{session_id}/trim": "Trim the cache for a session",
    "POST /cache/{session_id}/update-summary": "Update session summary in the cache",
    "GET /cache/{session_id}/get-summary": "Get session summary from the cache",
    "DELETE /cache/{session_id}/clear": "Clear the cache for a session",
    "GET /health": "Health check for the Cache Service"
  }
}
```

---

## Data Types

### Common Types

- **string**: Text data
- **datetime**: ISO 8601 formatted datetime string (e.g., "2024-01-15T10:30:00")
- **boolean**: true or false
- **integer**: Numeric integer value

### Role Values

The `role` field in messages typically accepts:
- `"user"`: Messages from the user
- `"assistant"`: Messages from the AI assistant
- `"system"`: System messages

---

## Redis Data Structure

### Message Storage

Messages are stored in Redis using the LIST data structure:
- **Key Format**: `session:{session_id}:messages`
- **Data Format**: JSON strings containing `{"role": "...", "content": "..."}`
- **Operations**: `RPUSH` (add), `LRANGE` (retrieve), `LTRIM` (trim), `LLEN` (count)

### Summary Storage

Summaries are stored as simple string values:
- **Key Format**: `session:{session_id}:summary`
- **Data Format**: Plain text string
- **Operations**: `SET` (store), `GET` (retrieve), `DEL` (delete)

---

## Configuration

The Cache Service uses a `config.yaml` file for configuration:

```yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  decode_responses: true
  max_connections: 20

cache:
  message_limit: 10
```

### Configuration Parameters

- **redis.host**: Redis server hostname
- **redis.port**: Redis server port
- **redis.db**: Redis database number
- **redis.decode_responses**: Whether to decode responses as strings (recommended: true)
- **redis.max_connections**: Maximum number of connections in the connection pool
- **cache.message_limit**: Number of messages before summarization is triggered

---

## Integration Notes

### For Other Services

1. **Authentication**: Obtain a JWT access token from the User Service `/login` endpoint before calling Cache Service endpoints.

2. **Write-Through Strategy**: 
   - Messages should be written to both the Cache Service (for fast access) and the Chat Service (for persistence)
   - The Cache Service is a write-through cache, meaning it's used alongside the primary database

3. **Summarization Flow**:
   - When `needs_summarization` is `true` from `add_message` or `trim_cache`, trigger summarization
   - After summarization, update the summary using `update-summary`
   - Optionally trim the cache to keep only recent messages

4. **Session Management**:
   - Sessions should be created in the User Service before caching messages
   - Cache data is session-specific and isolated by `session_id`

5. **Error Handling**: Always check for:
   - `401 Unauthorized`: Re-authenticate and retry
   - `503 Service Unavailable`: Service may be starting up or Redis connection lost
   - `500 Internal Server Error`: Log error and retry with exponential backoff

6. **Cache Invalidation**: 
   - Use `clear_cache` when a session is deleted
   - Consider trimming cache periodically to manage memory usage

7. **CORS**: The service allows CORS from all origins. Configure appropriately for production.

---

## Example Usage

### Add a Message to Cache

```bash
curl -X POST "http://localhost:8003/cache/session-123/message" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Hello, how are you?"
  }'
```

**Response**:
```json
{
  "message": "Message added successfully",
  "needs_summarization": false
}
```

### Get Cached Messages

```bash
curl -X GET "http://localhost:8003/cache/session-123/messages?limit=5" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
[
  {
    "role": "user",
    "content": "Hello, how are you?",
    "timestamp": null
  },
  {
    "role": "assistant",
    "content": "I'm doing well, thank you!",
    "timestamp": null
  }
]
```

### Get Message Count

```bash
curl -X GET "http://localhost:8003/cache/session-123/message_count" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "count": 10
}
```

### Trim Cache

```bash
curl -X DELETE "http://localhost:8003/cache/session-123/trim?keep_last=5" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "message": "Cache trimmed successfully",
  "needs_summarization": true
}
```

### Update Summary

```bash
curl -X POST "http://localhost:8003/cache/session-123/update-summary" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "User asked about weather and received information about sunny conditions."
  }'
```

**Response**:
```json
{
  "message": "Session summary updated successfully",
  "success": true
}
```

### Get Summary

```bash
curl -X GET "http://localhost:8003/cache/session-123/get-summary" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "summary": "User asked about weather and received information about sunny conditions.",
  "success": true
}
```

### Clear Cache

```bash
curl -X DELETE "http://localhost:8003/cache/session-123/clear" \
  -H "Authorization: Bearer <access_token>"
```

**Response**:
```json
{
  "message": "Cache cleared successfully",
  "success": true
}
```

### Health Check

```bash
curl -X GET "http://localhost:8003/health"
```

**Response**:
```json
{
  "status": "healthy",
  "details": {
    "status": "Cache service is operational"
  }
}
```

---

## Typical Workflow

### Message Caching Workflow

1. **Add Message**: Call `POST /cache/{session_id}/message` to cache a new message
2. **Check Summarization**: If `needs_summarization` is `true`, trigger summarization process
3. **Update Summary**: After summarization, call `POST /cache/{session_id}/update-summary` to store the summary
4. **Trim Cache**: Optionally call `DELETE /cache/{session_id}/trim?keep_last=N` to remove old messages
5. **Retrieve Messages**: Use `GET /cache/{session_id}/messages` for fast access to recent messages

### Cache Management

- **Periodic Trimming**: Trim cache periodically to manage Redis memory usage
- **Session Cleanup**: Clear cache when sessions are deleted
- **Summary Updates**: Update summaries after summarization completes

---

## Performance Considerations

1. **Redis Connection Pool**: The service uses a connection pool for efficient Redis access
2. **Message Limit**: Configure `message_limit` based on your memory constraints and summarization frequency
3. **Trimming Strategy**: Trim cache after summarization to keep only essential messages
4. **TTL Consideration**: Consider implementing TTL (Time To Live) for cache entries if needed

---

## Security Considerations

1. **Authentication**: All endpoints (except `/health` and `/`) require valid JWT tokens
2. **Session Isolation**: Cache data is isolated by `session_id` - users can only access their own sessions
3. **Redis Security**: Ensure Redis is properly secured (password authentication, network restrictions)
4. **Token Validation**: User ID is extracted from JWT token - ensure tokens are properly validated

---

## Error Scenarios

### Redis Connection Lost

If Redis connection is lost:
- Health check will return `503 Service Unavailable`
- All cache operations will fail with `500 Internal Server Error`
- Service will attempt to reconnect automatically (with retry logic)

### Cache Miss

If messages are not in cache:
- `get_messages` returns an empty array
- `get_summary` returns `null` for summary
- Fallback to Chat Service for data retrieval

### Memory Management

If Redis memory is full:
- Redis may evict keys based on eviction policy
- Consider implementing TTL or more aggressive trimming
- Monitor Redis memory usage

