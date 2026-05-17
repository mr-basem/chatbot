# Kemet AI Chatbot

A production-grade AI chatbot for the Kemet tourism platform, built with Streamlit, MiniMax, and MySQL.

## Features
- **Natural Language Interface**: Ask questions naturally in English.
- **RAG-powered SQL Generation**: Uses a local FAISS vector store to inject schema and business rules into the LLM context.
- **Safe SQL Execution**: Uses `sqlglot` for parsing and validation, ensuring only `SELECT` queries run against an allowed set of tables.
- **MiniMax Integration**: Uses the OpenAI-compatible MiniMax API.
- **Clean UI**: Built with Streamlit, including a debug mode for viewing raw SQL and tabular data.

## Project Structure
```
/app
    app.py                     # Streamlit frontend & pipeline
    config.py                  # Environment config
    database/
        connection.py          # SQLAlchemy connection pooling
    prompts/
        templates.py           # LLM prompts
    rag/
        embeddings.py          # Sentence-transformers wrapper
        vector_store.py        # FAISS implementation
    services/
        llm.py                 # MiniMax API client with retries
        text_to_sql.py         # RAG + LLM orchestration
        response_formatter.py  # Data to natural text conversion
    sql/
        validator.py           # SQLGlot safety validation
        executor.py            # Pandas SQL execution
    utils/
        logger.py              # Centralized logging
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   # Edit .env with your MiniMax API key and MySQL URL
   ```

3. **Run the App**:
   ```bash
   streamlit run app/main.py
   ```
