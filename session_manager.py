"""Session Manager for generating and managing chat session IDs."""

import uuid
from datetime import datetime
from typing import Optional


class SessionManager:
    """Manages chat session identifiers."""
    
    def __init__(self):
        """Initialize the session manager."""
        self.current_session_id: Optional[str] = None
        self.current_user_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
    
    def create_new_session(self, user_id: str) -> str:
        """
        Create a new chat session with a unique ID for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Session ID string
        """
        self.current_session_id = str(uuid.uuid4())
        self.current_user_id = user_id
        self.session_start_time = datetime.now()
        
        print(f"[Session] Created new session: {self.current_session_id} for user: {user_id}")
        return self.current_session_id
    
    def get_current_session_id(self) -> Optional[str]:
        """
        Get the current session ID.
        
        Returns:
            Current session ID or None if no session exists
        """
        return self.current_session_id
    
    def get_current_user_id(self) -> Optional[str]:
        """
        Get the current user ID.
        
        Returns:
            Current user ID or None if no session exists
        """
        return self.current_user_id
    
    def get_session_duration(self) -> Optional[float]:
        """
        Get the duration of the current session in seconds.
        
        Returns:
            Duration in seconds or None if no session exists
        """
        if self.session_start_time:
            return (datetime.now() - self.session_start_time).total_seconds()
        return None
    
    def end_session(self) -> None:
        """End the current session."""
        if self.current_session_id:
            duration = self.get_session_duration()
            print(f"[Session] Ended session {self.current_session_id} (duration: {duration:.2f}s)")
            self.current_session_id = None
            self.current_user_id = None
            self.session_start_time = None
    
    def get_session_info(self) -> dict:
        """
        Get information about the current session.
        
        Returns:
            Dictionary with session ID, user ID, start time, and duration
        """
        return {
            'session_id': self.current_session_id,
            'user_id': self.current_user_id,
            'start_time': self.session_start_time.isoformat() if self.session_start_time else None,
            'duration_seconds': self.get_session_duration()
        }
