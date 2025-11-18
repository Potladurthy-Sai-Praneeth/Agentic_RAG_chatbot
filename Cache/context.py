from contextvars import ContextVar
from typing import Optional, Dict

current_jwt_token: ContextVar[Dict] = ContextVar("current_jwt_token", default={})