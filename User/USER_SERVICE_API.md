# User Service API Documentation

## Overview

The User Service API is a FastAPI-based microservice for managing user authentication, registration, and session management. It uses PostgreSQL for data persistence and provides JWT-based authentication.

**Base URL**: `http://localhost:8001`  
**Version**: 1.0.0

---

## Authentication

Most endpoints require JWT Bearer token authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

The token is obtained from the `/login` endpoint. The token payload contains:
- `sub`: User ID
- `type`: "access"
- `exp`: Expiration timestamp
- `iat`: Issued at timestamp

---

## Endpoints

### 1. Register User

**Endpoint**: `POST /register`

**Description**: Register a new user account with email, username, and password.

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "password123"
}
```

**Request Model**: `RegisterRequestModel`
- `email` (EmailStr, required): Valid email address
- `username` (string, required): Unique username
- `password` (string, required): Password (minimum 8 characters)

**Response**: `201 Created`

**Response Model**: `RegisterResponseModel`
```json
{
  "success": true,
  "message": "string"
}
```

**Response Fields**:
- `success` (boolean): Indicates if the registration was successful
- `message` (string): Detailed message about the registration outcome

**Note**: The actual API returns `message` field, though the Pydantic model defines `description`. This may cause validation issues.

**Error Responses**:
- `400 Bad Request`: Invalid data or user already exists
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- Email and username must be unique
- Password is hashed using SHA-256 with a random salt
- User ID is automatically generated

---

### 2. Login

**Endpoint**: `POST /login`

**Description**: Authenticate a user and receive JWT access and refresh tokens.

**Authentication**: Not required

**Request Body**:
```json
{
  "user": "user@example.com",
  "password": "password123"
}
```

**Request Model**: `LoginRequestModel`
- `user` (string, required): User's email or username
- `password` (string, required): User's password

**Response**: `200 OK`

**Response Model**: `LoginResponseModel`
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Response Fields**:
- `access_token` (string): JWT access token for API authentication
- `refresh_token` (string): JWT refresh token for obtaining new access tokens
- `token_type` (string): Token type, always "bearer"
- `expires_in` (integer): Access token expiration time in seconds

**Error Responses**:
- `401 Unauthorized`: Invalid email/username or password combination
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- Login updates the `last_login` timestamp for the user
- Access token expiration is configurable (default: 60 minutes)
- Refresh token expiration is configurable (default: 7 days)

---

### 3. Add Session

**Endpoint**: `POST /add-session`

**Description**: Add a new session to the authenticated user's profile.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "session_id": "session-123"
}
```

**Request Model**: `AddSessionRequestModel`
- `session_id` (string, required): The session ID to be added to the user profile

**Response**: `200 OK`

**Response Model**: `AddSessionResponseModel`
```json
{
  "success": true,
  "message": "string"
}
```

**Response Fields**:
- `success` (boolean): Indicates if the session addition was successful
- `message` (string): Detailed message about the session addition outcome

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Failed to add session (e.g., session already exists or user doesn't exist)
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- User ID is extracted from the JWT token
- Session ID must be unique
- Session creation timestamp is automatically set

---

### 4. Get Sessions

**Endpoint**: `GET /get-sessions`

**Description**: Retrieve all sessions associated with the authenticated user.

**Authentication**: Required (Bearer Token)

**Response**: `200 OK`

**Response Model**: `GetSessionsResponseModel`
```json
{
  "success": true,
  "sessions": [
    {
      "session_id": "string",
      "created_at": "datetime"
    }
  ]
}
```

**Response Fields**:
- `success` (boolean): Indicates if the retrieval was successful
- `sessions` (array): List of session objects, each containing:
  - `session_id` (string): Unique session identifier
  - `created_at` (datetime): Timestamp when the session was created

**Note**: The actual API returns `sessions` as an array of objects with `session_id` and `created_at` fields, though the Pydantic model defines it as `Dict[str, datetime]`. The runtime behavior returns a list of dictionaries.

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- Returns an empty array if the user has no sessions
- Sessions are ordered by creation time

---

### 5. Delete Session

**Endpoint**: `DELETE /delete-session`

**Description**: Delete a specific session from the authenticated user's profile.

**Authentication**: Required (Bearer Token)

**Request Body**:
```json
{
  "session_id": "session-123"
}
```

**Request Model**: `DeleteSessionRequestModel`
- `session_id` (string, required): The session ID to be deleted from the user profile

**Response**: `200 OK`

**Response Model**: `DeleteSessionResponseModel`
```json
{
  "success": true,
  "message": "string"
}
```

**Response Fields**:
- `success` (boolean): Indicates if the session deletion was successful
- `message` (string): Detailed message about the session deletion outcome

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Failed to delete session (session not found)
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- User ID is extracted from the JWT token
- Only sessions belonging to the authenticated user can be deleted

---

### 6. Delete User

**Endpoint**: `DELETE /delete-user`

**Description**: Delete the authenticated user's account and all associated sessions.

**Authentication**: Required (Bearer Token)

**Request Body**: None

**Response**: `200 OK`

**Response Model**: `DeleteUserResponseModel`
```json
{
  "success": true,
  "message": "string"
}
```

**Response Fields**:
- `success` (boolean): Indicates if the user deletion was successful
- `message` (string): Detailed message about the user deletion outcome

**Error Responses**:
- `401 Unauthorized`: Invalid or missing authentication token
- `400 Bad Request`: Failed to delete user account (user not found)
- `503 Service Unavailable`: User database service is not available
- `500 Internal Server Error`: Internal server error

**Notes**:
- User ID is extracted from the JWT token
- This operation cascades to delete all associated sessions
- This is a permanent operation

---

### 7. Health Check

**Endpoint**: `GET /health`

**Description**: Check the health status of the User Management Service.

**Authentication**: Not required

**Response**: `200 OK`

**Response Model**: `HealthCheckResponseModel`
```json
{
  "status": "healthy",
  "message": "string"
}
```

**Response Fields**:
- `status` (string): Health status (e.g., "healthy")
- `message` (string): Detailed health check message

**Error Responses**:
- `503 Service Unavailable`: User database service is not available/unhealthy
- `500 Internal Server Error`: Internal server error during health check

---

### 8. Root Endpoint

**Endpoint**: `GET /`

**Description**: Welcome endpoint that provides service information and available endpoints.

**Authentication**: Not required

**Response**: `200 OK`

**Response**:
```json
{
  "service": "User Management Service",
  "status": "running",
  "version": "1.0.0",
  "endpoints": {
    "POST /register": "Register a new user",
    "POST /login": "Login a user",
    "POST /add-session": "Add a new session",
    "GET /get-sessions": "Retrieve all sessions for a user",
    "DELETE /delete-session": "Delete a session",
    "DELETE /delete-user": "Delete user account",
    "GET /health": "Health Check Endpoint"
  }
}
```

---

## Data Types

### Common Types

- **string**: Text data
- **EmailStr**: Valid email address format (validated by Pydantic)
- **datetime**: ISO 8601 formatted datetime string (e.g., "2024-01-15T10:30:00")
- **boolean**: true or false
- **integer**: Numeric integer value

### Password Requirements

- Minimum length: 8 characters
- Passwords are hashed using SHA-256 with a random salt
- Original passwords are never stored

---

## Database Schema

### Users Table

- `user_id` (VARCHAR(64), PRIMARY KEY): Unique user identifier
- `user_email` (VARCHAR(255), UNIQUE, NOT NULL): User's email address
- `username` (VARCHAR(150), UNIQUE, NOT NULL): User's username
- `password_hash` (VARCHAR(256), NOT NULL): Hashed password
- `salt` (VARCHAR(64), NOT NULL): Salt used for password hashing
- `created_at` (TIMESTAMP, NOT NULL): Account creation timestamp
- `last_login` (TIMESTAMP): Last login timestamp

### User Sessions Table

- `session_id` (VARCHAR(64), PRIMARY KEY): Unique session identifier
- `user_id` (VARCHAR(64), NOT NULL, FOREIGN KEY): Reference to users table
- `created_at` (TIMESTAMP, NOT NULL): Session creation timestamp

---

## Integration Notes

### For Other Services

1. **Authentication Flow**:
   - Call `/login` endpoint with user credentials
   - Receive `access_token` and `refresh_token`
   - Use `access_token` in Authorization header for protected endpoints
   - Use `refresh_token` to obtain new access tokens when expired

2. **User ID Format**: User IDs are hexadecimal strings (64 characters) generated using `secrets.token_hex(32)`

3. **Session Management**:
   - Sessions must be created in User Service before being used in Chat Service
   - Session IDs should be unique across all users
   - Sessions are automatically deleted when a user account is deleted (CASCADE)

4. **Error Handling**:
   - `401 Unauthorized`: Token expired or invalid - re-authenticate
   - `400 Bad Request`: Invalid input data or resource conflict
   - `503 Service Unavailable`: Service may be starting up or database connection lost
   - `500 Internal Server Error`: Log error and retry with exponential backoff

5. **CORS**: The service allows CORS from all origins. Configure appropriately for production.

6. **JWT Token Structure**:
   ```json
   {
     "sub": "user_id_here",
     "type": "access",
     "exp": 1234567890,
     "iat": 1234567890
   }
   ```

---

## Example Usage

### Register a User

```bash
curl -X POST "http://localhost:8001/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "securepass123"
  }'
```

### Login

```bash
curl -X POST "http://localhost:8001/login" \
  -H "Content-Type: application/json" \
  -d '{
    "user": "user@example.com",
    "password": "securepass123"
  }'
```

### Add Session

```bash
curl -X POST "http://localhost:8001/add-session" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-abc-123"
  }'
```

### Get Sessions

```bash
curl -X GET "http://localhost:8001/get-sessions" \
  -H "Authorization: Bearer <access_token>"
```

### Delete Session

```bash
curl -X DELETE "http://localhost:8001/delete-session" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-abc-123"
  }'
```

### Delete User

```bash
curl -X DELETE "http://localhost:8001/delete-user" \
  -H "Authorization: Bearer <access_token>"
```

---

## Security Considerations

1. **Password Security**: Passwords are hashed with SHA-256 and a random salt. Never store plaintext passwords.

2. **JWT Tokens**: 
   - Access tokens have a short expiration time (default: 60 minutes)
   - Refresh tokens have a longer expiration time (default: 7 days)
   - Tokens should be stored securely on the client side

3. **Token Validation**: Always validate token type ("access" vs "refresh") and expiration before processing requests.

4. **Database Security**: Ensure PostgreSQL credentials are stored securely using environment variables.

5. **CORS Configuration**: Update CORS settings for production to restrict allowed origins.

