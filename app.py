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

# Custom CSS for pulsing animation
st.markdown("""
<style>
@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}

.pulse-box {
    animation: pulse 1.5s ease-in-out infinite;
}

.status-box {
    padding: 1rem;
    border-radius: 8px;
    background-color: #f0f2f6;
    border: 1px solid #ddd;
    margin-bottom: 1rem;
}

.status-box.thinking {
    background-color: #e3f2fd;
    border-color: #1976d2;
}

.status-box.ready {
    background-color: #f0f2f6;
    border-color: #ddd;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'agent_steps' not in st.session_state:
    st.session_state.agent_steps = []
if 'current_tokens' not in st.session_state:
    st.session_state.current_tokens = 0
if 'agent_status' not in st.session_state:
    st.session_state.agent_status = "ready"
if 'agent_current_step' not in st.session_state:
    st.session_state.agent_current_step = ""
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
    
    # Agent Status Box
    status_container = st.container()
    with status_container:
        if st.session_state.agent_status == "thinking":
            st.markdown(f"""
            <div class="status-box thinking pulse-box">
                <h3 style="margin: 0;">🔍 {st.session_state.agent_current_step or "Analysiere..."}</h3>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #666;">Agent arbeitet...</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-box ready">
                <h3 style="margin: 0;">💬 Chat-Modus</h3>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #666;">Bereit für Gespräch</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Token Counter
    st.metric("Tokens (aktuelle Anfrage)", st.session_state.current_tokens)
    
    # Agent Steps
    st.markdown("### 🤖 Agent Thinking")
    
    # Display steps
    if st.session_state.agent_steps:
        for i, step in enumerate(st.session_state.agent_steps):
            with st.expander(f"Step {i+1}: {step['type']}", expanded=(i == len(st.session_state.agent_steps) - 1)):
                st.code(step['content'], language="text")
    else:
        st.info("Warte auf Anfrage...")
    
    # Clear steps button
    if st.button("Clear History", type="secondary"):
        st.session_state.agent_steps = []
        st.session_state.current_tokens = 0
        st.session_state.agent_status = "ready"
        st.session_state.agent_current_step = ""

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
    st.session_state.agent_status = "thinking"
    st.session_state.agent_current_step = "Starte Analyse"
    
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
                # Create status container for live updates
                status_container = st.container()
                progress_placeholder = status_container.empty()
                
                def update_sidebar(step_type, content):
                    st.session_state.agent_steps.append({
                        "type": step_type,
                        "content": content
                    })
                    
                    # Update agent status
                    st.session_state.agent_status = "thinking"
                    
                    # Translate step types to German
                    step_translations = {
                        "Intent Classification": "Klassifiziere Anfrage",
                        "Date Enhancement": "Verarbeite Zeitangaben",
                        "API URL Generation": "Generiere API-Abfrage",
                        "API Request": "Rufe Daten ab",
                        "API Response": "Verarbeite Antwort",
                        "Summarization": "Erstelle Zusammenfassung",
                        "Token Count": "Zähle Tokens"
                    }
                    
                    st.session_state.agent_current_step = step_translations.get(step_type, step_type)
                    
                    # Show progress in chat area with steps
                    progress_text = f"🔄 **{st.session_state.agent_current_step}...**\n\n"
                    progress_text += "**Bisherige Schritte:**\n"
                    for i, step in enumerate(st.session_state.agent_steps):
                        step_name = step_translations.get(step['type'], step['type'])
                        progress_text += f"{'✅' if i < len(st.session_state.agent_steps)-1 else '⏳'} {step_name}\n"
                    
                    progress_placeholder.info(progress_text)
                    
                    # Extract token count if available
                    if step_type == "Token Count":
                        # Extract total tokens from format "Total: X tokens ..."
                        tokens = int(content.split("Total: ")[1].split(" tokens")[0])
                        st.session_state.current_tokens = tokens
                
                response = asyncio.run(process_user_query(
                    st.session_state.kernel, 
                    prompt,
                    update_sidebar
                ))
                
                # Clear progress completely
                progress_placeholder.empty()
                status_container.empty()
                
                # Show final answer
                if response:
                    st.markdown(response)
                    
                    # Show token count below answer
                    if st.session_state.current_tokens > 0:
                        st.caption(f"📊 Verbrauchte Tokens: {st.session_state.current_tokens}")
                else:
                    st.error("Keine Antwort erhalten")
                
                # Reset status to ready
                st.session_state.agent_status = "ready"
                st.session_state.agent_current_step = ""
            except Exception as e:
                response = f"❌ Ein Fehler ist aufgetreten: {str(e)}"
                st.error(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})