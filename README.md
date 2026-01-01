# LangChain SQL Agent Demo
A guide to building a question-answer chatbot with LangChain and PostgreSQL with session memory

## Prerequisites

-   Python 3.9+
-   PostgreSQL database
-   OpenAI API key
-   Basic knowledge of SQL and Python

## Setup

First, install the required packages:

```bash
pip install fastapi uvicorn langchain-openai langchain-community sqlalchemy psycopg2-binary langchain-postgres asyncio
```

For our example, let's assume we have a simple **bookstore database** with two tables:

```sql
-- Authors table
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    birth_year INTEGER,
    nationality VARCHAR(100)
);

-- Books table  
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    author_id INTEGER REFERENCES authors(id),
    genre VARCHAR(100),
    publication_year INTEGER,
    rating DECIMAL(3,2)
);
```

-   **Authors**: stores basic author information like name, year of birth, and nationality.
-   **Books**: stores book details such as title, genre, publication year, and rating, with a foreign key linking back to the author.

Once you create these tables and insert some sample data, it helps to also define a **view** called `books_with_authors`. This view joins both tables into one unified dataset so that queries can be simplified. Instead of writing complex SQL joins every time, the agent can query the view directly to get books along with their authors.

```sql
CREATE VIEW books_with_authors AS
SELECT 
    b.id AS book_id,
    b.title,
    b.genre,
    b.publication_year,
    b.rating,
    a.name AS author_name,
    a.birth_year,
    a.nationality
FROM books b
JOIN authors a ON b.author_id = a.id;
```

# Running the Application

## Setup Steps

1.  **Create your database**
2.  **Clone the project** with `https://github.com/Silversky-Technology/langchain-sql-agent-guide.git`
3.  **Configure credentials** - Replace OpenAI API key and your database credentials
4.  **Set up virtual environment** - In your project folder terminal, run:
    
    
    ```bash
    python -m venv venv
    ```
    
5.  **Activate virtual environment** (for Mac):
    

    
    ```bash
    source venv/bin/activate
    ```
    
6.  **Install dependencies** in the virtual environment:
   
   ```bash
    pip install fastapi uvicorn langchain-openai langchain-community sqlalchemy psycopg2-binary langchain-postgres asyncio
   ```
    
    
7.  **Run the application**:
    
    
    ```bash
    uvicorn main:app --reload
    ```
    

## Testing the API

Your API will be available at `http://localhost:8000`. You can test it with:



```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many authors do we have?",
    "user_id": "3dc035ae-bc72-4d5a-8569-c87c10aab97f"
  }'
```

