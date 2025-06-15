import os
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.functions import KernelArguments
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.prompt_template import InputVariable
# import tiktoken  # Optional - install with: pip install tiktoken
from skills.graph_api_request import GraphAPIRequestSkill
from config.date_helper import enhance_prompt_with_date


def build_kernel() -> Kernel:
    """Build and configure the Semantic Kernel instance"""
    
    # Initialize kernel
    kernel = Kernel()
    
    # Configure Azure OpenAI
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    
    if not all([deployment_name, endpoint, api_key]):
        raise ValueError("Azure OpenAI configuration missing. Please check your .env file.")
    
    # Add Azure OpenAI chat service with correct API version for o3-mini
    service_id = "chat-gpt"
    kernel.add_service(
        AzureChatCompletion(
            service_id=service_id,
            deployment_name=deployment_name,
            endpoint=endpoint,
            api_key=api_key,
            api_version="2024-12-01-preview",  # Required for o3-mini model
        )
    )
    
    # Import semantic functions
    skills_directory = os.path.join(os.path.dirname(__file__), "..", "skills")
    
    # Import GraphAPIBuilder prompt
    with open(os.path.join(skills_directory, "graph_api_builder", "GraphAPIBuilder.skprompt.txt"), "r", encoding="utf-8") as f:
        graph_api_builder_prompt = f.read()
    
    graph_api_builder_config = PromptTemplateConfig(
        template=graph_api_builder_prompt,
        name="GraphAPIBuilder",
        description="Generate Graph API URLs from natural language queries",
        input_variables=[
            InputVariable(
                name="input",
                description="The user's natural language query",
                is_required=True,
            )
        ],
    )
    
    graph_api_builder_function = kernel.add_function(
        plugin_name="graph_api_builder",
        function_name="GraphAPIBuilder",
        prompt_template_config=graph_api_builder_config,
    )
    
    # Import Summarizer prompt
    with open(os.path.join(skills_directory, "summarizer", "Summarizer.skprompt.txt"), "r", encoding="utf-8") as f:
        summarizer_prompt = f.read()
    
    summarizer_config = PromptTemplateConfig(
        template=summarizer_prompt,
        name="Summarizer",
        description="Summarize Graph API responses for users",
        input_variables=[
            InputVariable(
                name="question",
                description="The original user question",
                is_required=True,
            ),
            InputVariable(
                name="apiResponse",
                description="The Graph API JSON response",
                is_required=True,
            )
        ],
    )
    
    summarizer_function = kernel.add_function(
        plugin_name="summarizer",
        function_name="Summarizer",
        prompt_template_config=summarizer_config,
    )
    
    # Import Intent Classifier prompt
    with open(os.path.join(skills_directory, "intent_classifier", "IntentClassifier.skprompt.txt"), "r", encoding="utf-8") as f:
        intent_classifier_prompt = f.read()
    
    intent_classifier_config = PromptTemplateConfig(
        template=intent_classifier_prompt,
        name="IntentClassifier",
        description="Classify user intent",
        input_variables=[
            InputVariable(
                name="input",
                description="The user's message",
                is_required=True,
            )
        ],
    )
    
    intent_classifier_function = kernel.add_function(
        plugin_name="intent_classifier",
        function_name="IntentClassifier",
        prompt_template_config=intent_classifier_config,
    )
    
    # Import native plugin
    graph_skill = GraphAPIRequestSkill(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET")
    )
    kernel.add_plugin(graph_skill, "GraphAPIRequest")
    
    return kernel


def estimate_tokens(text: str, model="gpt-4") -> int:
    """Estimate token count"""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except:
        # Fallback to character estimation if tiktoken not installed
        # Rough estimate: 1 token ≈ 4 characters for English, 2 for German
        return len(text) // 3

async def process_user_query(kernel: Kernel, user_query: str, step_callback=None) -> str:
    """
    Process user query through the agent pipeline:
    0. Check intent - only use Graph API for relevant queries
    1. Generate Graph API URL
    2. Execute API request
    3. Summarize response
    """
    
    total_tokens = 0
    
    try:
        # Step 0: Check user intent
        intent_classifier = kernel.get_function("intent_classifier", "IntentClassifier")
        intent_result = await kernel.invoke(
            intent_classifier,
            KernelArguments(input=user_query)
        )
        intent = str(intent_result).strip()
        
        # Track tokens
        intent_prompt = f"Du bist ein Intent-Klassifizierer...\nBenutzerfrage: {user_query}\n..."
        total_tokens += estimate_tokens(intent_prompt) + estimate_tokens(intent)
        
        # Debug logging and callback
        print(f"User Query: {user_query}")
        print(f"Detected Intent: {intent}")
        
        if step_callback:
            step_callback("Intent Classification", f"Query: {user_query}\nIntent: {intent}")
        
        # If it's a general query, respond as a normal chatbot
        if intent == "GENERAL":
            # Use GPT to generate a friendly response
            chat_prompt = f"""Du bist ein freundlicher Assistent. Beantworte die folgende Frage oder reagiere angemessen:

Benutzer: {user_query}

Assistent:"""
            
            chat_config = PromptTemplateConfig(
                template=chat_prompt,
                name="GeneralChat",
                description="General chat response",
            )
            
            chat_function = kernel.add_function(
                plugin_name="general_chat",
                function_name="GeneralChat",
                prompt_template_config=chat_config,
            )
            
            response = await kernel.invoke(chat_function)
            return str(response)
        
        # For GRAPH_API queries, proceed with the normal flow
        # Step 1: Generate Graph API URL with enhanced date handling
        enhanced_query = enhance_prompt_with_date(user_query)
        
        if step_callback:
            step_callback("Date Enhancement", f"Enhanced Query: {enhanced_query}")
        
        # Track tokens for date enhancement
        total_tokens += estimate_tokens(enhanced_query)
        
        api_builder = kernel.get_function("graph_api_builder", "GraphAPIBuilder")
        api_url_result = await kernel.invoke(
            api_builder,
            KernelArguments(input=enhanced_query)
        )
        api_path = str(api_url_result).strip()
        
        # Track tokens for API generation
        api_prompt = f"Du bist ein Experte für die Microsoft Graph API...\nBenutzerfrage: {enhanced_query}\n..."
        total_tokens += estimate_tokens(api_prompt) + estimate_tokens(api_path)
        
        if step_callback:
            step_callback("API URL Generation", f"Generated URL: {api_path}")
        
        # Validate the API path
        if not api_path or api_path == "None":
            return "❌ Fehler: Konnte keine gültige Graph API URL generieren."
    
        # Step 2: Execute Graph API request
        if step_callback:
            step_callback("API Request", f"Calling: https://graph.microsoft.com/v1.0{api_path}")
            
        graph_request = kernel.get_function("GraphAPIRequest", "execute_graph_request")
        api_response = await kernel.invoke(
            graph_request,
            KernelArguments(api_path=api_path)
        )
        
        if step_callback:
            # Truncate response for display
            response_preview = str(api_response)[:500] + "..." if len(str(api_response)) > 500 else str(api_response)
            step_callback("API Response", response_preview)
        
        # Step 3: Summarize the response
        if step_callback:
            step_callback("Summarization", "Generating user-friendly response...")
            
        summarizer = kernel.get_function("summarizer", "Summarizer")
        summary = await kernel.invoke(
            summarizer,
            KernelArguments(
                question=user_query,
                apiResponse=str(api_response)
            )
        )
        
        final_response = str(summary)
        
        # Track tokens for summarization
        summary_prompt = f"Du bist ein präziser Assistent...\nOriginalfrage: {user_query}\nAPI-Antwort: {str(api_response)}\n..."
        total_tokens += estimate_tokens(summary_prompt) + estimate_tokens(final_response)
        
        # Add tokens for API response
        total_tokens += estimate_tokens(str(api_response))
        
        if step_callback:
            step_callback("Token Count", f"Total: {total_tokens} tokens (Input: {total_tokens - estimate_tokens(final_response)}, Output: {estimate_tokens(final_response)})")
        
        return final_response
        
    except Exception as e:
        return f"❌ Fehler bei der Verarbeitung: {str(e)}"