import os
from dotenv import load_dotenv
from rag import RAGChatbot
from config import *

load_dotenv()



def main():
    """Main function to run the RAG chatbot."""
    print(f"Welcome I am {CHAT_BOT_NAME}!. I am here to help you with information about {NAME}.")
    print("Type 'exit' to quit the chat.")

    chatbot = RAGChatbot()
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(f"{CHAT_BOT_NAME}: Goodbye!")
                break
            
            if not user_input.strip():
                continue
            
            # Get response from agent
            response = chatbot.chat(user_input)
            
            # Display response
            print(f"{CHAT_BOT_NAME}: {response}")
        
        except KeyboardInterrupt:
            print(f"\n{CHAT_BOT_NAME}: Goodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {type(e).__name__}: {e}")



if __name__ == "__main__":
    main()