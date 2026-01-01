import os
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from sqlalchemy import create_engine

# Setup
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"  # Replace with your actual OpenAI API key
DB_URI = "postgresql+psycopg2://user:password@localhost:5432/bookstore"

# Create database connection
engine = create_engine(DB_URI)

# Define custom table info for better LLM context
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
        "- rating (DECIMAL): Book rating (0–5)\n"
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

# Initialize SQLDatabase with view support and custom info
db = SQLDatabase(
    engine=engine,
    include_tables=list(custom_table_info.keys()),
    custom_table_info=custom_table_info,
    view_support=True
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

# Test it out
response = agent.invoke({"input": "List all books with their authors and ratings"})
print(response["output"])