import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
from config.kernel_builder import build_kernel, process_user_query

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="GraphGPT - Microsoft 365 Chat Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'agent_steps' not in st.session_state:
    st.session_state.agent_steps = []
if 'current_tokens' not in st.session_state:
    st.session_state.current_tokens = 0
if 'kernel' not in st.session_state:
    try:
        st.session_state.kernel = build_kernel()
    except ValueError as e:
        st.error(f"❌ Konfigurationsfehler: {str(e)}")
        st.info("Bitte stellen Sie sicher, dass alle Umgebungsvariablen in der .env Datei konfiguriert sind.")
        st.stop()

# Sidebar
with st.sidebar:
    st.title("🔍 Agent Monitor")
    
    # Token Counter
    st.metric("Tokens (aktuelle Anfrage)", st.session_state.current_tokens)
    
    # Agent Steps
    st.markdown("### 🤖 Agent Thinking")
    
    if st.session_state.agent_steps:
        for i, step in enumerate(st.session_state.agent_steps):
            with st.expander(f"Step {i+1}: {step['type']}", expanded=True):
                st.code(step['content'], language="text")
    else:
        st.info("Warte auf Anfrage...")
    
    # Clear steps button
    if st.button("Clear History", type="secondary"):
        st.session_state.agent_steps = []
        st.session_state.current_tokens = 0

# Main area
st.title("GraphGPT - Microsoft 365 Chat Agent")
st.markdown("### Stellen Sie Fragen zu Ihrer Microsoft 365 Umgebung")

# New chat button
if st.button("Neuen Chat starten", type="secondary"):
    st.session_state.messages = []
    st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ihre Frage..."):
    # Reset agent steps for new query
    st.session_state.agent_steps = []
    st.session_state.current_tokens = 0
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Denke nach..."):
            try:
                # Process user query through Semantic Kernel with monitoring
                def update_sidebar(step_type, content):
                    st.session_state.agent_steps.append({
                        "type": step_type,
                        "content": content
                    })
                    # Extract token count if available
                    if step_type == "Token Estimate":
                        tokens = int(content.split("~")[1].split(" ")[0])
                        st.session_state.current_tokens = tokens
                
                response = asyncio.run(process_user_query(
                    st.session_state.kernel, 
                    prompt,
                    update_sidebar
                ))
                st.markdown(response)
            except Exception as e:
                response = f"❌ Ein Fehler ist aufgetreten: {str(e)}"
                st.error(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})