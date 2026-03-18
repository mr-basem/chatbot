import streamlit as st
import pandas as pd
import google.generativeai as genai
import sqlite3

# Gemini API
genai.configure(api_key="AIzaSyDrdkbpD6irv4oQE6rPlmnmz7WK4lSwbgk")

model = genai.GenerativeModel("gemini-2.5-flash")

# load db
@st.cache_data
def load_data():
    conn = sqlite3.connect("kemet.db")
    df_places = pd.read_sql_query("SELECT * FROM places", conn)
    df_events = pd.read_sql_query("SELECT * FROM events", conn)
    conn.close()
    return df_places, df_events

df_places, df_events = load_data()

# Initialize session state for user selection
if "category" not in st.session_state:
    st.session_state.category = None

# If user hasn't chosen a category yet, show the two big buttons directly!
if st.session_state.category is None:
    st.title("Welcome to Kemet AI")
    st.markdown("### What would you like to ask about today?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🌍 Places", use_container_width=True):
            st.session_state.category = "Places"
            st.rerun()  # Forces the page to instantly hide the buttons and load the chat!
            
    with col2:
        if st.button("🎉 Events", use_container_width=True):
            st.session_state.category = "Events"
            st.rerun()

# If user HAS chosen a category, hide the buttons and show the chatbot page
else:
    # Get current chosen category
    category = st.session_state.category
    
    st.title(f"AI Chatbot for {category}")
    
    # Adding a clean button at the top to let them go back to the selection screen
    if st.button("⬅️ Change Category"):
        st.session_state.category = None
        st.session_state.messages = [] # Optional: clears their chat history upon switching topic
        st.rerun()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input(f"Ask about Kemet {category}..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Load ONLY the correct dataset text based on the current active category!
        if category == "Places":
            data_text = f"Places Database:\n{df_places.to_string()}"
        else:
            data_text = f"Events Database:\n{df_events.to_string()}"

        # Build conversation history
        conversation_history = ""
        for msg in st.session_state.messages[:-1]:  # Exclude the current prompt since we add it below
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_history += f"{role}: {msg['content']}\n\n"

        # Create the full prompt based on the user's question, dataset, and history
        full_prompt = f"""
        You are Kemet AI, a highly professional Egyptian tourism and cultural assistant.

        CRITICAL RULES FOR YOUR RESPONSES:
        1. Keep responses EXTREMELY SHORT, concise, and straight to the point. No long paragraphs. Use a maximum of 2-3 brief sentences unless listing items.
        2. Speak directly to the client professionally. Do NOT mention words like "dataset", "database", or "context". 
        3. If a location or event is missing, politely say: "I apologize, but I don't have information about [Item] right now. Can I help you with another location?"
        4. Use elegant formatting (like bullet points and subtle emojis) only when necessary for readability. Avoid overwhelming the client with text.

        Knowledge Base:
        {data_text}

        Conversation History:
        {conversation_history}

        Latest Question from the client:
        {prompt}
        
        Respond naturally, professionally, and briefly:
        """

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response.text})