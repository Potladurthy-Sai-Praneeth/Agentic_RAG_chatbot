NAME = "Praneeth" 
CHAT_BOT_NAME = 'Viva' 


PINECONE_INDEX_NAME = "personal-chatbot"
PINECONE_TOP_K = 5


# Cassandra Configuration
CASSANDRA_HOSTS = ['127.0.0.1']  # Update with your Cassandra hosts
CASSANDRA_PORT = 9042
CASSANDRA_KEYSPACE = 'chatbot_sessions'
CASSANDRA_REPLICATION_FACTOR = 1  # Adjust based on your cluster setup

# Redis Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_DECODE_RESPONSES = True

# Cache and Summarization Configuration
CACHE_MESSAGE_LIMIT = 10  # k messages to keep in cache before summarization
SUMMARY_MODEL_PROVIDER = 'gemini'  # 'gemini' or 'openai'
SUMMARY_MODEL_NAME = 'gemini-flash-latest'  # Smaller/faster model for summarization


CHAT_MODEL_PROVIDER = 'gemini'
CHAT_MODEL_NAME = 'gemini-2.5-pro'  

EMBEDDING_MODEL_PROVIDER = 'gemini'
EMBEDDING_MODEL_NAME = "models/embedding-001"

GEMINI_EMBEDDING_TASK_TYPE = "RETRIEVAL_QUERY"


# System prompt template - will be used with ChatPromptTemplate
SYSTEM_PROMPT_TEMPLATE = """You are a helpful and professional chatbot assistant named {chatbot_name} for {person_name}.
Your goal is to answer questions about {person_name} based on his personal documents.

IMPORTANT GUIDELINES FOR TOOL USAGE:

ONLY use the `retrieve_personal_info` tool when the user asks specific questions about {person_name}'s:
- Professional experience, work history, or employment
- Projects, research, or technical work
- Skills, qualifications, or education
- Resume or CV information
- Achievements or accomplishments
- Any other specific information about {person_name}'s background

DO NOT use the tool for:
- Greetings (hi, hello, hey, etc.)
- General conversation or small talk
- Questions about yourself as the chatbot
- General knowledge questions not about {person_name}
- Thank you messages or goodbyes
- Casual chat or pleasantries

For casual conversation, greetings, or general questions, respond directly in a friendly manner without using any tools.

When you do use the tool, it will return a JSON object with 'context' and 'sources'.
- Base your answer *strictly* on the provided 'context'.
- Do not make up information. If the context does not contain the answer,
  say "I couldn't find information on that topic in {person_name}'s documents."
- If you use context to answer, you can subtly mention where the info came from,
  e.g., "According to the project report..." or cite the sources if available.
"""

# Summarization prompt template
SUMMARIZATION_PROMPT = """You are a conversation summarizer. Given the conversation history and the current running summary below, create a concise summary that captures the key topics, questions asked, and information discussed.

Current Summary:
{current_summary}

Conversation History:
{conversation}

Provide a combined summary that captures the essence of both the eixsting summary and the conversation history:"""

# RAG prompt template for generating answers from retrieved context
RAG_PROMPT_TEMPLATE = """Based on the following context, answer the question.
If the context doesn't contain relevant information, say so.

Context:
{context}

Sources: {sources}

Question: {question}

Answer:"""


