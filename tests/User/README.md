# UserService Test Suite

This directory contains comprehensive tests for the `UserService` class.

## Test Coverage

The test suite covers all methods and functionality of the `UserService` class:

### Test Classes

1. **TestUserServiceInitialization** - Tests for service initialization
2. **TestUserServiceInitialize** - Tests for database initialization
3. **TestUserServiceRegisterUser** - Tests for user registration
4. **TestUserServiceLogin** - Tests for user authentication
5. **TestUserServiceAddSession** - Tests for adding user sessions
6. **TestUserServiceGetSessions** - Tests for retrieving user sessions
7. **TestUserServiceDeleteSession** - Tests for deleting sessions
8. **TestUserServiceDeleteUser** - Tests for deleting users
9. **TestUserServiceHealthCheck** - Tests for health check functionality
10. **TestUserServicePasswordHashing** - Tests for password hashing
11. **TestUserServiceContextManager** - Tests for async context manager
12. **TestUserServiceEdgeCases** - Tests for edge cases and boundary conditions

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r tests/User/requirements.txt
```

### Run All Tests

```bash
pytest tests/User/test_user_service.py -v
```

### Run Specific Test Class

```bash
pytest tests/User/test_user_service.py::TestUserServiceLogin -v
```

### Run Specific Test

```bash
pytest tests/User/test_user_service.py::TestUserServiceLogin::test_login_success_with_username -v
```

### Run with Coverage

```bash
pytest tests/User/test_user_service.py --cov=User.user_service --cov-report=html
```

## Test Structure

- **conftest.py**: Contains pytest fixtures for mocking database connections and creating test data
- **test_user_service.py**: Contains all test cases organized by functionality
- **ANALYSIS.md**: Documents issues and inconsistencies found in the UserService implementation

## Key Test Scenarios

### Success Cases
- User registration with valid data
- User login with username or email
- Session management (add, get, delete)
- User deletion
- Health check when database is available

### Error Cases
- Registration with duplicate email/username
- Login with incorrect credentials
- Operations when database pool is not initialized
- Database connection errors
- Non-existent user/session operations

### Edge Cases
- Empty strings
- Missing database pool
- Concurrent operations
- Invalid data formats

## Issues Identified

See `ANALYSIS.md` for a detailed list of issues and inconsistencies found in the UserService implementation, including:

1. Missing `connect()` method (API calls it but it doesn't exist)
2. SQL Foreign Key syntax error
3. Insecure password hashing (SHA-256 instead of bcrypt)
4. Missing input validation
5. Inconsistent error handling

## Notes

- All tests use mocked database connections to avoid requiring a real database
- Tests are designed to be fast and isolated
- The test suite uses `pytest-asyncio` for async test support
- Mock objects simulate asyncpg database behavior

