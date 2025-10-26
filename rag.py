import os
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent

from config import *
from tools import *

load_dotenv()



class RAGChatbot:
    def __init__(self):
        self.chat_model = get_chat_model()
        self.tools = get_tools()
        self.vectorstore = get_vectorstore()
        
        self.chat_history = []

        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT_TEMPLATE.format(chatbot_name=CHAT_BOT_NAME, person_name=NAME)),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        self.agent = create_tool_calling_agent(
            llm=self.chat_model,
            tools=self.tools,
            prompt=self.agent_prompt,
        )

        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            return_intermediate_steps=False
        )

    def chat(self, user_input: str) -> str:
        """Chat with the RAG chatbot."""
        response = self.agent_executor.invoke({
            "input": user_input,
            "chat_history": self.chat_history
        })
        
        # Extract the actual output string from the response
        output = response.get("output", str(response))
        
        self.chat_history.append(HumanMessage(content=user_input))
        self.chat_history.append(AIMessage(content=output))
        return output