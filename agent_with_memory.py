import asyncio
import os
import psycopg
from sqlalchemy import create_engine
from langchain_postgres import PostgresChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

# Setup
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"  # Replace with your actual OpenAI API key
DB_URI = "postgresql+psycopg2://user:password@localhost:5432/bookstore"
CHAT_HISTORY_CONN = "postgresql://user:password@localhost:5432/bookstore"
CHAT_HISTORY_TABLE = "chat_history"
psycopg_conn = psycopg.connect(CHAT_HISTORY_CONN)

# Run this only once
# try:
#     PostgresChatMessageHistory.create_tables(CHAT_HISTORY_CONN, CHAT_HISTORY_TABLE)
#     print(f"Chat history table '{CHAT_HISTORY_TABLE}' created or already exists")
# except Exception as e:
#     print(f"Note: {e}")

# Database setup
engine = create_engine(DB_URI)
db = SQLDatabase(
    engine=engine,
)
# Initialize LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Create toolkit and agent
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

async def get_session_history(session_id: str) -> PostgresChatMessageHistory:
    """Get chat history for a session"""
    async_conn = await psycopg.AsyncConnection.connect(CHAT_HISTORY_CONN)
    return PostgresChatMessageHistory(
        CHAT_HISTORY_TABLE,
        session_id,
        async_connection=async_conn
    )

async def get_memory(session_id: str) -> ConversationBufferMemory:
    """Create memory with PostgreSQL backing"""
    chat_history = await get_session_history(session_id)
    return ConversationBufferMemory(
        chat_memory=chat_history,
        memory_key="history", 
        return_messages=True
    )

async def format_history(chat_history, max_messages: int = 6):
    """Format recent chat history for context"""
    messages = await chat_history.aget_messages()
    recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
    
    formatted = []
    for msg in recent_messages:
        role = "User" if msg.type == "human" else "Assistant"
        formatted.append(f"{role}: {msg.content}")
    
    return "\n".join(formatted)

async def create_agent_with_memory(session_id: str):
    """Create agent with conversation memory"""
    memory = await get_memory(session_id)
    
    # Get formatted history for context
    readable_history = await format_history(memory.chat_memory, 6)
    
    # Custom prompt with history
    custom_prefix = f"""
    You are a helpful assistant that can answer questions about a bookstore database.
    You have access to information about books and authors.
    
    Previous conversation context:
    {readable_history}
    
    Be concise and helpful in your responses.
    """
    
    return create_sql_agent(
        toolkit=toolkit,
        llm=llm,
        agent_type="tool-calling",
        prefix=custom_prefix,
        agent_executor_kwargs={"memory": memory},
        verbose=True
    )

# Usage with memory
import asyncio

async def chat_example():
    agent = await create_agent_with_memory("3dc035ae-bc72-4d5a-8569-c87c10aab97f") # Must be a UUID
    
    # First question
    response1 = await agent.ainvoke({"input": "How many books by Jane Austen do we have?"})
    print("Response 1:", response1["output"])
    
    # Follow-up question (will remember context)
    response2 = await agent.ainvoke({"input": "What genres are they?"})
    print("Response 2:", response2["output"])

# Run the example
asyncio.run(chat_example())