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
    status_box_placeholder = st.empty()
    
    # Token Counter
    token_metric_placeholder = st.empty()

# Update sidebar display function
def update_sidebar_display():
    with status_box_placeholder:
        if st.session_state.agent_status == "thinking":
            # Get the latest step details for more context
            detail_text = "Agent arbeitet..."
            if st.session_state.agent_steps:
                latest_step = st.session_state.agent_steps[-1]
                step_content = latest_step.get('content', '')
                
                # Extract meaningful details from step content
                if latest_step['type'] == "API Request":
                    if "Calling:" in step_content:
                        url = step_content.split("Calling: ")[-1]
                        detail_text = f"Rufe API auf: {url.split('/')[-1]}"
                    elif "Versuch" in step_content:
                        detail_text = step_content
                elif latest_step['type'] == "API URL Generation":
                    if "Generated URL:" in step_content or "URL generiert:" in step_content:
                        url = step_content.split(": ")[-1]
                        detail_text = f"URL erstellt: {url.split('/')[-1]}"
                elif latest_step['type'] == "Error Correction":
                    detail_text = step_content
                elif latest_step['type'] == "Intent Classification":
                    if "Intent:" in step_content:
                        intent = step_content.split("Intent: ")[-1]
                        detail_text = f"Erkannt als: {intent}"
                elif latest_step['type'] == "Date Enhancement":
                    if "Zeitfilter" in step_content:
                        detail_text = "Zeitfilter hinzugefügt"
                    elif "keine Zeitangaben" in step_content.lower():
                        detail_text = "Keine Zeitangaben erkannt"
                elif latest_step['type'] == "Summarization":
                    detail_text = "Erstelle nutzerfreundliche Antwort"
                else:
                    detail_text = step_content[:50] + "..." if len(step_content) > 50 else step_content
            
            st.markdown(f"""
            <div class="status-box thinking pulse-box">
                <h3 style="margin: 0;">🔍 {st.session_state.agent_current_step or "Analysiere..."}</h3>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #666;">{detail_text}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="status-box ready">
                <h3 style="margin: 0;">💬 Chat-Modus</h3>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; color: #666;">Bereit für Gespräch</p>
            </div>
            """, unsafe_allow_html=True)
    
    with token_metric_placeholder:
        st.metric("Tokens (aktuelle Anfrage)", st.session_state.current_tokens)

# Initial sidebar display
update_sidebar_display()

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
                    # Avoid duplicates - check if this exact step was already added
                    if (st.session_state.agent_steps and 
                        st.session_state.agent_steps[-1]["type"] == step_type and
                        st.session_state.agent_steps[-1]["content"] == content):
                        return
                    
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
                        "Token Count": "Zähle Tokens",
                        "Error Correction": "Korrigiere Fehler"
                    }
                    
                    st.session_state.agent_current_step = step_translations.get(step_type, step_type)
                    
                    # Show progress in chat area with steps - remove duplicates
                    unique_steps = []
                    seen_types = set()
                    for step in st.session_state.agent_steps:
                        if step['type'] not in seen_types:
                            unique_steps.append(step)
                            seen_types.add(step['type'])
                        else:
                            # Update existing step if it's the same type
                            for i, existing_step in enumerate(unique_steps):
                                if existing_step['type'] == step['type']:
                                    unique_steps[i] = step
                                    break
                    
                    progress_text = f"🔄 **{st.session_state.agent_current_step}...**\n\n"
                    progress_text += "**Bisherige Schritte:**\n"
                    for i, step in enumerate(unique_steps):
                        step_name = step_translations.get(step['type'], step['type'])
                        progress_text += f"{'✅' if i < len(unique_steps)-1 else '⏳'} {step_name}\n"
                    
                    progress_placeholder.info(progress_text)
                    
                    # Extract token count if available
                    if step_type == "Token Count":
                        # Extract total tokens from format "Total: X tokens ..."
                        tokens = int(content.split("Total: ")[1].split(" tokens")[0])
                        st.session_state.current_tokens = tokens
                    
                    # Force sidebar update
                    update_sidebar_display()
                
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
                
                # Update sidebar to show ready state
                update_sidebar_display()
            except Exception as e:
                response = f"❌ Ein Fehler ist aufgetreten: {str(e)}"
                st.error(response)
                
                # Reset status to ready even on error
                st.session_state.agent_status = "ready"
                st.session_state.agent_current_step = ""
                update_sidebar_display()
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})