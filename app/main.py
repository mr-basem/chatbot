import sys
from pathlib import Path

# Add the project root to sys.path so 'app' can be imported
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

import streamlit as st
import time
from app.config import Config
from app.services.llm import MiniMaxService
from app.services.llm import LLMAuthError, LLMServiceError
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore
from app.sql.validator import SQLValidator
from app.services.text_to_sql import TextToSQLService
from app.sql.executor import QueryExecutor
from app.services.response_formatter import ResponseFormatter
from app.services.query_classifier import QueryIntent, classify
from app.services.query_cache import cache_stats
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

st.set_page_config(
    page_title="Kemet AI Tour Guide",
    page_icon="🐪",
    layout="centered"
)

# Custom premium CSS styling to give a professional "wow" effect and match Egyptian theme
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    .stApp {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main-title {
        font-weight: 700;
        font-size: 2.8rem;
        background: linear-gradient(135deg, #D4AF37 0%, #F5D76E 50%, #B8860B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
        text-shadow: 0 4px 20px rgba(212, 175, 55, 0.15);
    }
    
    .subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #8C8C8C;
        margin-bottom: 2rem;
    }
    
    .stExpander {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(212, 175, 55, 0.2);
        border-radius: 12px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .stExpander:hover {
        border-color: rgba(212, 175, 55, 0.5);
    }
    
    div[data-testid="stChatMessage"] {
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid transparent;
        transition: all 0.3s ease;
    }
    
    /* Golden glow border for Assistant and glassmorphism for user */
    div[data-testid="stChatMessage"]:nth-child(even) {
        background: rgba(212, 175, 55, 0.04);
        border: 1px solid rgba(212, 175, 55, 0.1);
    }
    
    div[data-testid="stChatMessage"]:nth-child(odd) {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    textarea[data-testid="stChatInputTextArea"] {
        border-radius: 12px !important;
        border: 1px solid rgba(212, 175, 55, 0.2) !important;
    }
    textarea[data-testid="stChatInputTextArea"]:focus {
        border-color: #D4AF37 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Services lazily
@st.cache_resource
def init_services():
    llm_service = MiniMaxService()
    emb_service = EmbeddingService()
    vector_store = VectorStore(emb_service)
    sql_validator = SQLValidator()
    text_to_sql_service = TextToSQLService(llm_service, vector_store, sql_validator)
    query_executor = QueryExecutor()
    response_formatter = ResponseFormatter(llm_service)
    return text_to_sql_service, query_executor, response_formatter

try:
    text_to_sql, executor, formatter = init_services()
except Exception as e:
    st.error(f"Failed to initialize services: {e}")
    st.stop()

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome to Kemet! 🐪 Ask me about tourist places, events, or ticket prices in Egypt."}
    ]

# Display Title and Config using custom premium HTML
st.markdown("<h1 class='main-title'>🇪🇬 Kemet AI Tour Guide</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Explore Egypt with natural language. Ask about places, events, or ticket prices!</p>", unsafe_allow_html=True)

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Where would you like to go?"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Use classifier to detect greetings (replaces manual is_greeting)
                if classify(prompt) == QueryIntent.GREETING:
                    response_text = (
                        "Hello! I am **Kemet**, your Egyptian AI Tour Guide. 🐪✨\n\n"
                        "I can help you search and explore historical tourist destinations, events, categories, and ticket prices in Egypt.\n\n"
                        "Feel free to ask me questions like:\n"
                        "- 🏛️ *'historical places in Luxor'*\n"
                        "- 💰 *'places in Cairo under 500 EGP'*\n"
                        "- 📅 *'events in Giza'*\n\n"
                        "How can I help you plan your journey today?"
                    )
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    st.stop()

                # 1. Generate SQL
                start_time = time.time()
                sql_query = text_to_sql.generate_sql(prompt)
                sql_elapsed = time.time() - start_time
                
                # 2. Execute SQL
                df = executor.execute(sql_query)
                db_elapsed = time.time() - start_time - sql_elapsed
                
                # 3. Format Response
                response_text = formatter.format_response(prompt, df)
                
                # 4. Stream response word-by-word for natural feel
                def _stream_words(text: str):
                    """Yield words with a small delay for streaming effect."""
                    for word in text.split(" "):
                        yield word + " "
                        time.sleep(0.018)

                st.write_stream(_stream_words(response_text))
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response_text,
                    "sql": sql_query,
                })
                
                total = time.time() - start_time
                logger.info(
                    f"Request done in {total:.2f}s "
                    f"(sql={sql_elapsed:.3f}s, db={db_elapsed:.3f}s) "
                    f"| cache={cache_stats()}"
                )
                
            except ValueError as ve:
                response_text = "I couldn't process that request securely. Please ask about tourist places, events, or ticket prices!"
                st.markdown(response_text)
                logger.warning(f"Validation error: {ve}")
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except LLMAuthError as e:
                response_text = (
                    "I am currently having trouble connecting to my conversational AI brain. 🐪✨\n\n"
                    "However, my database lookup is fully functional! Please ask me a query focused on places, events, or prices, such as:\n"
                    "- *'historical places in Luxor'*\n"
                    "- *'places in Cairo under 500 EGP'*\n"
                    "- *'events in Giza'*"
                )
                st.markdown(response_text)
                logger.error(f"LLM auth error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except LLMServiceError as e:
                response_text = (
                    "I'm experiencing a brief connection drop with my conversational AI brain. 🐪✨\n\n"
                    "You can still search our tourist database directly! Try asking something like:\n"
                    "- *'historical places in Luxor'*\n"
                    "- *'places in Cairo under 500 EGP'*\n"
                    "- *'events in Giza'*"
                )
                st.markdown(response_text)
                logger.error(f"LLM service error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except Exception as e:
                response_text = (
                    "I encountered an error trying to process that request. 🐪\n"
                    "Please make sure your question is related to tourist places, events, or ticket prices in Egypt!"
                )
                st.markdown(response_text)
                logger.error(f"Pipeline error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": response_text})
