"""User Authentication Manager using SQLite for user management."""

import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path


class AuthManager:
    """Manages user authentication and authorization."""
    
    def __init__(self, db_path: str = "users.db"):
        """
        Initialize the authentication manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create users table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"[AuthManager] Database initialized at {self.db_path}")
    
    def _hash_password(self, password: str, salt: str) -> str:
        """
        Hash a password with salt using SHA-256.
        
        Args:
            password: Plain text password
            salt: Salt for hashing
            
        Returns:
            Hashed password
        """
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def register_user(self, username: str, password: str) -> Optional[str]:
        """
        Register a new user.
        
        Args:
            username: Unique username
            password: User's password
            
        Returns:
            User ID if successful, None otherwise
        """
        if not username or not password:
            print("[AuthManager] Username and password cannot be empty")
            return None
        
        # Generate user ID and salt
        user_id = secrets.token_hex(16)
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (user_id, username, password_hash, salt)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, password_hash, salt))
            
            conn.commit()
            conn.close()
            
            print(f"[AuthManager] User '{username}' registered successfully")
            return user_id
        
        except sqlite3.IntegrityError:
            print(f"[AuthManager] Username '{username}' already exists")
            return None
        except Exception as e:
            print(f"[AuthManager] Error registering user: {e}")
            return None
    
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user and return user ID.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User ID if authentication successful, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, password_hash, salt
                FROM users
                WHERE username = ?
            """, (username,))
            
            result = cursor.fetchone()
            
            if not result:
                print(f"[AuthManager] User '{username}' not found")
                conn.close()
                return None
            
            user_id, stored_hash, salt = result
            password_hash = self._hash_password(password, salt)
            
            if password_hash == stored_hash:
                # Update last login time
                cursor.execute("""
                    UPDATE users
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                conn.close()
                
                print(f"[AuthManager] User '{username}' logged in successfully")
                return user_id
            else:
                print(f"[AuthManager] Invalid password for user '{username}'")
                conn.close()
                return None
        
        except Exception as e:
            print(f"[AuthManager] Error during login: {e}")
            return None
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """
        Get user information.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user information or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, username, created_at, last_login
                FROM users
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'user_id': result[0],
                    'username': result[1],
                    'created_at': result[2],
                    'last_login': result[3]
                }
            return None
        
        except Exception as e:
            print(f"[AuthManager] Error getting user info: {e}")
            return None
    
    def get_username(self, user_id: str) -> Optional[str]:
        """
        Get username from user ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Username or None
        """
        user_info = self.get_user_info(user_id)
        return user_info['username'] if user_info else None
    
    def user_exists(self, username: str) -> bool:
        """
        Check if a username exists.
        
        Args:
            username: Username to check
            
        Returns:
            True if username exists, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM users WHERE username = ?
            """, (username,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
        
        except Exception as e:
            print(f"[AuthManager] Error checking user existence: {e}")
            return False
