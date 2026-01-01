import os
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from sqlalchemy import create_engine
from langchain.callbacks.base import BaseCallbackHandler

# Setup
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"  # Replace with your actual OpenAI API key
DB_URI = "postgresql+psycopg2://user:password@localhost:5432/bookstore"

# Create database connection
engine = create_engine(DB_URI)

class SQLResultHandler(BaseCallbackHandler):
    """Callback handler to capture raw SQL query results"""
    
    def __init__(self):
        self.latest_sql_result = None
        self.sql_run_ids = set()
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        """Track SQL tool starts"""
        tool_name = serialized.get('name', 'unknown') if isinstance(serialized, dict) else str(serialized)
        if tool_name == "sql_db_query":
            run_id = kwargs.get('run_id')
            self.sql_run_ids.add(run_id)
            
    def on_tool_end(self, output, **kwargs):
        """Capture SQL tool output"""
        run_id = kwargs.get('run_id')
        parent_run_id = kwargs.get('parent_run_id')
        
        # Check if this is a SQL tool end
        if run_id in self.sql_run_ids or parent_run_id in self.sql_run_ids:
            self.latest_sql_result = output
            
            # Clean up run IDs
            self.sql_run_ids.discard(run_id)
            self.sql_run_ids.discard(parent_run_id)
            
    def on_tool_error(self, error, **kwargs):
        """Clean up on SQL tool errors"""
        run_id = kwargs.get('run_id')
        self.sql_run_ids.discard(run_id)
    
    def get_latest_result(self):
        """Get the most recent SQL result"""
        return self.latest_sql_result
    
    def reset(self):
        """Reset for next query"""
        self.latest_sql_result = None
        self.sql_run_ids = set()

# Usage with callback
sql_handler = SQLResultHandler()
# Initialize SQLDatabase with view support and custom info
db = SQLDatabase(
    engine=engine,
)
# Initialize LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Create toolkit and agent
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
agent = create_sql_agent(
    toolkit=toolkit,
    llm=llm,
    agent_type="tool-calling",
    verbose=True
)

response = agent.invoke(
    {"input": "Show me all science fiction books"},
    {"callbacks": [sql_handler]}
)

print("Agent Response:", response["output"])
print("Raw SQL Result:", sql_handler.get_latest_result())