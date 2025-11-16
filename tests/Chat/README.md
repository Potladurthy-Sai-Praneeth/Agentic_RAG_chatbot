# ChatService Test Suite

This directory contains comprehensive tests for the `ChatService` class and Chat API endpoints.

## Test Coverage

The test suite covers all methods and functionality of the `ChatService` class and API endpoints:

### Test Classes

1. **TestChatServiceInitialization** - Tests for service initialization
2. **TestChatServiceInitialize** - Tests for database initialization
3. **TestChatServiceStoreMessage** - Tests for storing chat messages
4. **TestChatServiceGetMessages** - Tests for retrieving chat messages
5. **TestChatServiceGetSummary** - Tests for retrieving session summaries
6. **TestChatServiceInsertSummary** - Tests for inserting session summaries
7. **TestChatServiceGetMessageCount** - Tests for retrieving message counts
8. **TestChatServiceDeleteSession** - Tests for deleting sessions
9. **TestChatServiceHealthCheck** - Tests for health check functionality
10. **TestChatServiceClose** - Tests for closing connections
11. **TestChatServiceContextManager** - Tests for async context manager
12. **TestChatServiceEdgeCases** - Tests for edge cases and boundary conditions
13. **TestChatAPIStoreMessage** - Tests for POST /chat/{session_id}/add-message endpoint
14. **TestChatAPIGetMessages** - Tests for GET /chat/{session_id}/get-messages endpoint
15. **TestChatAPIGetSummary** - Tests for GET /chat/{session_id}/get-summary endpoint
16. **TestChatAPIInsertSummary** - Tests for POST /chat/{session_id}/insert-summary endpoint
17. **TestChatAPIGetMessageCount** - Tests for GET /chat/{session_id}/get-message-count endpoint
18. **TestChatAPIDeleteSession** - Tests for DELETE /chat/{session_id}/delete endpoint
19. **TestChatAPIHealthCheck** - Tests for GET /health endpoint
20. **TestChatAPIRoot** - Tests for GET / endpoint

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r tests/Chat/requirements.txt
```

### Run All Tests

```bash
pytest tests/Chat/test_chat_service.py tests/Chat/test_chat_api.py -v
```

### Run Specific Test Class

```bash
pytest tests/Chat/test_chat_service.py::TestChatServiceStoreMessage -v
```

### Run Specific Test

```bash
pytest tests/Chat/test_chat_service.py::TestChatServiceStoreMessage::test_store_message_success -v
```

### Run with Coverage

```bash
pytest tests/Chat/ --cov=Chat.chat_service --cov=Chat.chat_api --cov-report=html
```

## Test Structure

- **conftest.py**: Contains pytest fixtures for mocking database connections and creating test data
- **test_chat_service.py**: Contains all test cases for ChatService class organized by functionality
- **test_chat_api.py**: Contains all test cases for Chat API endpoints
- **requirements.txt**: Test dependencies

## Key Test Scenarios

### Success Cases
- Message storage and retrieval
- Session summary management
- Message count retrieval
- Session deletion
- Health check when database is available

### Error Cases
- Operations when service is not initialized
- Database connection errors
- Non-existent session operations
- Authentication failures

### Edge Cases
- Empty strings
- Missing service initialization
- Concurrent operations
- Invalid data formats

## Notes

- All tests use mocked database connections to avoid requiring a real Cassandra database
- Tests are designed to be fast and isolated
- The test suite uses `pytest-asyncio` for async test support
- Mock objects simulate Cassandra database behavior
- API tests use `TestClient` from FastAPI for endpoint testing

