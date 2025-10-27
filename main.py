import os
import sys
from dotenv import load_dotenv
from rag import RAGChatbot
from config import *
from auth_manager import AuthManager

load_dotenv()


def show_welcome_menu():
    """Display welcome menu for login/register."""
    print("=" * 60)
    print(f"Welcome to {CHAT_BOT_NAME} - AI Assistant for {NAME}")
    print("=" * 60)
    print("1. Login")
    print("2. Register new account")
    print("3. Exit")
    print("-" * 60)


def register_user(auth_manager: AuthManager) -> bool:
    """
    Handle user registration.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if registration successful, False otherwise
    """
    print("\n--- User Registration ---")
    username = input("Enter username: ").strip()
    
    if not username:
        print("Username cannot be empty!")
        return False
    
    if auth_manager.user_exists(username):
        print(f"Username '{username}' already exists. Please try logging in.")
        return False
    
    password = input("Enter password: ").strip()
    
    if not password:
        print("Password cannot be empty!")
        return False
    
    confirm_password = input("Confirm password: ").strip()
    
    if password != confirm_password:
        print("Passwords do not match!")
        return False
    
    user_id = auth_manager.register_user(username, password)
    
    if user_id:
        print(f"\n✓ Registration successful! Welcome, {username}!")
        return True
    else:
        print("\n✗ Registration failed. Please try again.")
        return False


def login_user(auth_manager: AuthManager) -> tuple:
    """
    Handle user login.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        Tuple of (user_id, username) if successful, (None, None) otherwise
    """
    print("\n--- User Login ---")
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    
    user_id = auth_manager.login(username, password)
    
    if user_id:
        print(f"\n✓ Login successful! Welcome back, {username}!")
        return user_id, username
    else:
        print("\n✗ Login failed. Invalid username or password.")
        return None, None


def main():
    """Main function to run the RAG chatbot with user authentication."""
    auth_manager = AuthManager()
    user_id = None
    username = None
    
    # Authentication loop
    while not user_id:
        show_welcome_menu()
        choice = input("Select an option (1-3): ").strip()
        
        if choice == "1":
            user_id, username = login_user(auth_manager)
        elif choice == "2":
            if register_user(auth_manager):
                # After successful registration, prompt for login
                print("\nPlease login with your new account.")
                user_id, username = login_user(auth_manager)
        elif choice == "3":
            print("Goodbye!")
            return
        else:
            print("Invalid option. Please select 1, 2, or 3.")
    
    # Chat session starts after successful authentication
    print("\n" + "=" * 60)
    print(f"Welcome, {username}! I am {CHAT_BOT_NAME}.")
    print(f"I am here to help you with information about {NAME}.")
    print("=" * 60)
    print("\nCommands:")
    print("  'exit' or 'quit' - End the chat session")
    print("  'logout' - Logout and return to login screen")
    print("-" * 60)

    chatbot = None
    try:
        chatbot = RAGChatbot(user_id=user_id)
        print(f"\n[Session ID: {chatbot.get_session_id()}]")
        print(f"[User: {username}]")
        print("-" * 60)
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print(f"{CHAT_BOT_NAME}: Goodbye, {username}!")
                    break
                
                if user_input.lower() == 'logout':
                    print(f"{CHAT_BOT_NAME}: Logging out...")
                    if chatbot:
                        chatbot.close()
                    # Restart main to show login screen
                    main()
                    return
                
                if not user_input:
                    continue
                
                # Get response from agent
                response = chatbot.chat(user_input)
                
                # Display response
                print(f"{CHAT_BOT_NAME}: {response}")
            
            except KeyboardInterrupt:
                print(f"\n{CHAT_BOT_NAME}: Goodbye, {username}!")
                break
            except Exception as e:
                print(f"\nAn error occurred: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
    
    finally:
        # Cleanup connections
        if chatbot:
            print("\n" + "-" * 60)
            print("Closing connections...")
            chatbot.close()




if __name__ == "__main__":
    main()