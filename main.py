from dotenv import load_dotenv
load_dotenv()   # 🔥 从 .env 加载 OPENAI_API_KEY

import os
import uuid
from typing import Optional

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine

from langchain.callbacks.base import BaseCallbackHandler
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_postgres import PostgresChatMessageHistory


# -----------------------------
# Safety check: API key must exist
# -----------------------------
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not found. Put it in .env (project root) or export it."


# -----------------------------
# Database config
# -----------------------------
DB_URI = "postgresql+psycopg2://user:password@localhost:5433/bookstore"
CHAT_HISTORY_CONN = "postgresql://user:password@localhost:5433/bookstore"
CHAT_HISTORY_TABLE = "chat_history"


# -----------------------------
# Deterministic session id (BEST PRACTICE)
# -----------------------------
# Fixed namespace: ensures same user_id -> same UUID across machines and restarts.
UUID_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

def stable_session_id(user_id: str) -> str:
    """
    Convert any human-readable user_id (e.g., 'Qun Li') into a stable UUID string.
    - Deterministic: same input -> same output
    - Cross-machine reproducible
    """
    if user_id is None:
        raise ValueError("user_id cannot be None")
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("user_id cannot be empty")
    return str(uuid.uuid5(UUID_NAMESPACE, user_id))


# -----------------------------
# SQL Database + LLM
# -----------------------------
engine = create_engine(DB_URI)

custom_table_info = {
    "authors": (
        "A table of authors.\n"
        "- id (SERIAL PRIMARY KEY): Unique ID of author\n"
        "- name (VARCHAR): Name of the author\n"
        "- birth_year (INTEGER): Year of birth\n"
        "- nationality (VARCHAR): Nationality of the author\n"
    ),
    "books": (
        "A table of books.\n"
        "- id (SERIAL PRIMARY KEY): Unique ID of book\n"
        "- title (VARCHAR): Title of the book\n"
        "- author_id (INTEGER): References authors(id)\n"
        "- genre (VARCHAR): Genre of the book\n"
        "- publication_year (INTEGER): Year of publication\n"
        "- rating (DECIMAL): Book rating (0–10)\n"
    ),
    "books_with_authors": (
        "A view combining books and authors.\n"
        "- book_id (INTEGER): ID of the book\n"
        "- title (VARCHAR): Title of the book\n"
        "- genre (VARCHAR): Genre of the book\n"
        "- publication_year (INTEGER): Year of publication\n"
        "- rating (DECIMAL): Rating of the book\n"
        "- author_name (VARCHAR): Name of the author\n"
        "- birth_year (INTEGER): Birth year of the author\n"
        "- nationality (VARCHAR): Nationality of the author\n"
    ),
}

db = SQLDatabase(
    engine=engine,
    include_tables=list(custom_table_info.keys()),
    custom_table_info=custom_table_info,
    view_support=True
)

# Use a model that is broadly available and cheaper for demos/interviews
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)


# -----------------------------
# SQL callback
# -----------------------------
class SQLResultHandler(BaseCallbackHandler):
    def __init__(self):
        self.latest_sql_result = None
        self.sql_run_ids = set()

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get('name', 'unknown') if isinstance(serialized, dict) else str(serialized)
        if tool_name == "sql_db_query":
            self.sql_run_ids.add(kwargs.get('run_id'))

    def on_tool_end(self, output, **kwargs):
        run_id = kwargs.get('run_id')
        if run_id in self.sql_run_ids:
            self.latest_sql_result = output
            self.sql_run_ids.discard(run_id)

    def get_latest_result(self):
        return self.latest_sql_result


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(title="SQL Chat Agent")


# ✅ Solution A: Ensure chat_history table exists at startup (idempotent)
@app.on_event("startup")
async def startup():
    try:
        # IMPORTANT:
        # In your installed version of langchain_postgres, create_tables expects
        # a DB connection object (has .cursor()), NOT a connection string.
        with psycopg.connect(CHAT_HISTORY_CONN) as conn:
            PostgresChatMessageHistory.create_tables(conn, CHAT_HISTORY_TABLE)

        print(f"✅ ensured table exists: {CHAT_HISTORY_TABLE}")
    except Exception as e:
        print(f"❌ failed to ensure chat history table: {e}")
        raise


# -----------------------------
# Memory
# -----------------------------
async def get_session_history(user_id: str):
    """
    LangChain PostgresChatMessageHistory requires session_id to be a valid UUID.
    We convert user_id -> deterministic UUIDv5.
    """
    session_id = stable_session_id(user_id)
    async_conn = await psycopg.AsyncConnection.connect(CHAT_HISTORY_CONN)

    return PostgresChatMessageHistory(
        CHAT_HISTORY_TABLE,
        session_id,
        async_connection=async_conn
    )

async def get_memory(user_id: str):
    chat_history = await get_session_history(user_id)
    return ConversationBufferMemory(
        chat_memory=chat_history,
        memory_key="history",
        return_messages=True
    )

async def create_agent_with_memory(user_id: str):
    memory = await get_memory(user_id)
    return create_sql_agent(
        toolkit=toolkit,
        llm=llm,
        agent_type="tool-calling",
        agent_executor_kwargs={"memory": memory},
        verbose=True
    )


# -----------------------------
# Schemas + Endpoint
# -----------------------------
class ChatRequest(BaseModel):
    message: str
    user_id: str

class ChatResponse(BaseModel):
    reply: str
    raw_sql_result: Optional[str] = None

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        sql_handler = SQLResultHandler()
        agent = await create_agent_with_memory(request.user_id)

        response = await agent.ainvoke(
            {"input": request.message},
            {"callbacks": [sql_handler]}
        )

        return ChatResponse(
            reply=response["output"],
            raw_sql_result=sql_handler.get_latest_result()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
