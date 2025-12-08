from contextvars import ContextVar
from typing import Optional, Dict

# Store both the decoded payload and the raw token string for forwarding
current_jwt_token: ContextVar[Dict] = ContextVar("current_jwt_token", default={})
current_jwt_token_string: ContextVar[Optional[str]] = ContextVar("current_jwt_token_string", default=None)