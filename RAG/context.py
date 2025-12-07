from contextvars import ContextVar

current_jwt_token: ContextVar[str] = ContextVar("current_jwt_token", default="")