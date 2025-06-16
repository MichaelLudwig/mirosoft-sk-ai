import os
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.functions import KernelArguments
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.prompt_template import InputVariable
# import tiktoken  # Optional - install with: pip install tiktoken
import json
from skills.graph_api_request_simplified import GraphAPIRequestSkill
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
    
    # Import Error Corrector prompt
    with open(os.path.join(skills_directory, "error_corrector", "ErrorCorrector.skprompt.txt"), "r", encoding="utf-8") as f:
        error_corrector_prompt = f.read()
    
    error_corrector_config = PromptTemplateConfig(
        template=error_corrector_prompt,
        name="ErrorCorrector",
        description="Correct failed Graph API URLs",
        input_variables=[
            InputVariable(
                name="original_query",
                description="The original user question",
                is_required=True,
            ),
            InputVariable(
                name="failed_url",
                description="The failed API URL",
                is_required=True,
            ),
            InputVariable(
                name="error_message",
                description="The error message",
                is_required=True,
            ),
            InputVariable(
                name="error_response",
                description="The full error response",
                is_required=True,
            )
        ],
    )
    
    error_corrector_function = kernel.add_function(
        plugin_name="error_corrector",
        function_name="ErrorCorrector",
        prompt_template_config=error_corrector_config,
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
        
        # Track tokens for intent classification
        intent_prompt_tokens = estimate_tokens(f"Du bist ein Intent-Klassifizierer für einen Microsoft 365 Chat-Assistenten.\nAnalysiere die Benutzerfrage SEHR GENAU...\nBenutzerfrage: {user_query}")
        intent_response_tokens = estimate_tokens(intent)
        intent_total_tokens = intent_prompt_tokens + intent_response_tokens
        total_tokens += intent_total_tokens
        
        # Debug logging and callback (commented out for performance)
        # print(f"User Query: {user_query}")
        # print(f"Detected Intent: {intent}")
        
        if step_callback:
            step_callback("Intent Classification", f"Query: {user_query}\nIntent: {intent}|||{intent_total_tokens}")
        
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
        # Track tokens for date enhancement (minimal, just processing)
        date_tokens = 5  # Minimal processing cost
        total_tokens += date_tokens
        
        enhanced_query = enhance_prompt_with_date(user_query)
        
        if step_callback:
            if enhanced_query != user_query:
                step_callback("Date Enhancement", f"Zeitfilter hinzugefügt: {enhanced_query}|||{date_tokens}")
            else:
                step_callback("Date Enhancement", f"Keine Zeitangaben gefunden - überspringe|||{date_tokens}")
        
        # Check if this is an app permissions query that needs multi-query approach
        is_app_permissions_query = any(keyword in user_query.lower() for keyword in [
            "rechte", "berechtigungen", "permissions", "zugeteilte rechte", "liste", "app registrierung"
        ]) and any(keyword in user_query.lower() for keyword in ["app", "anwendung", "registrierung"])
        
        print(f"DEBUG: App permissions query check: {is_app_permissions_query}")
        print(f"DEBUG: Query contains rechte keywords: {[k for k in ['rechte', 'berechtigungen', 'permissions', 'zugeteilte rechte', 'liste', 'app registrierung'] if k in user_query.lower()]}")
        print(f"DEBUG: Query contains app keywords: {[k for k in ['app', 'anwendung', 'registrierung'] if k in user_query.lower()]}")
        
        if is_app_permissions_query:
            # Multi-query approach like Lokka
            return await process_app_permissions_query(kernel, user_query, step_callback, total_tokens)
        
        # Regular single API call
        api_builder = kernel.get_function("graph_api_builder", "GraphAPIBuilder")
        api_url_result = await kernel.invoke(
            api_builder,
            KernelArguments(input=enhanced_query)
        )
        api_path = str(api_url_result).strip()
        
        # Track tokens for API generation - this is a major LLM call
        api_prompt_content = f"Du bist ein Experte für die Microsoft Graph API.\nAnalysiere die Benutzerfrage und generiere die passende Graph API URL.\n\nBenutzerfrage: {enhanced_query}\n\nWichtige Hinweise:\n- Verwende die korrekte Graph API v1.0 Syntax\n- Nutze OData-Filter für Zeitabfragen ($filter)\n- Verwende korrekte Datumsformate (ISO 8601)\n- Berechne relative Zeitangaben basierend auf dem heutigen Datum\n- Gib NUR die URL zurück, keine Erklärungen\n\nBeispiele für Benutzer-Abfragen:\n..."
        api_prompt_tokens = estimate_tokens(api_prompt_content)
        api_response_tokens = estimate_tokens(api_path)
        api_total_tokens = api_prompt_tokens + api_response_tokens
        total_tokens += api_total_tokens
        
        if step_callback:
            step_callback("API URL Generation", f"URL generiert: {api_path}|||{api_total_tokens}")
        
        # Validate the API path
        if not api_path or api_path == "None":
            return "❌ Fehler: Konnte keine gültige Graph API URL generieren."
    
        # Step 2: Execute Graph API request with retry mechanism
        max_retries = 3
        api_response = None
        
        for attempt in range(max_retries):
            if step_callback:
                step_callback("API Request", f"Versuch {attempt + 1}/{max_retries}: https://graph.microsoft.com/v1.0{api_path}|||0")
                
            # Determine if we need special parameters
            fetch_all = "alle" in user_query.lower() or "list" in user_query.lower()
            
            # ConsistencyLevel is auto-detected in the skill, but we can override here
            consistency_level = None
            if ("conditional access" in user_query.lower() or 
                "ca regeln" in user_query.lower() or 
                "richtlinien" in user_query.lower()):
                consistency_level = "eventual"
            
            graph_request = kernel.get_function("GraphAPIRequest", "execute_graph_request")
            api_response = await kernel.invoke(
                graph_request,
                KernelArguments(
                    api_path=api_path,
                    method="GET",
                    fetch_all=fetch_all,
                    consistency_level=consistency_level,
                    query_params={},
                    body={}
                )
            )
            
            # Check if response contains an error
            try:
                response_data = json.loads(str(api_response))
                # Check for API errors (status_code >= 400) or general errors
                has_error = ("error" in response_data and 
                           (response_data.get("status_code", 0) >= 400 or 
                            response_data.get("status_code") is None))
                
                if has_error:
                    if attempt < max_retries - 1:  # Not the last attempt
                        error_message = response_data.get("error", "Unknown error")
                        if step_callback:
                            step_callback("Error Correction", f"Fehler erkannt: {error_message[:50]}...|||0")
                        
                        # Try to correct the error
                        error_corrector = kernel.get_function("error_corrector", "ErrorCorrector")
                        corrected_url_result = await kernel.invoke(
                            error_corrector,
                            KernelArguments(
                                original_query=user_query,
                                failed_url=api_path,
                                error_message=error_message,
                                error_response=str(api_response)
                            )
                        )
                        
                        corrected_api_path = str(corrected_url_result).strip()
                        if corrected_api_path and corrected_api_path != api_path:
                            # Track tokens for error correction - this is another LLM call
                            error_prompt_content = f"Du bist ein Experte für Microsoft Graph API Fehlerkorrektur.\nAnalysiere den Fehler und korrigiere die API-URL.\n\nUrsprüngliche Anfrage: {user_query}\nFehlgeschlagene URL: {api_path}\nFehlermeldung: {error_message}\nFehlerdetails: {str(api_response)}"
                            error_prompt_tokens = estimate_tokens(error_prompt_content)
                            error_response_tokens = estimate_tokens(corrected_api_path)
                            error_total_tokens = error_prompt_tokens + error_response_tokens
                            total_tokens += error_total_tokens
                            
                            api_path = corrected_api_path
                            if step_callback:
                                step_callback("Error Correction", f"URL korrigiert zu: {api_path}|||{error_total_tokens}")
                            continue  # Retry with corrected URL
                        else:
                            if step_callback:
                                step_callback("Error Correction", f"Keine Korrektur möglich|||0")
                            break  # No correction possible
                    else:
                        break  # Last attempt, use the error response
                else:
                    break  # Success, exit retry loop
            except Exception as parse_error:
                # If we can't parse the response, treat it as an error
                if attempt < max_retries - 1:
                    if step_callback:
                        step_callback("Error Correction", f"Response-Parsing-Fehler: {str(parse_error)[:50]}...|||0")
                    break  # Can't parse response, can't retry meaningfully
                else:
                    break  # Last attempt
        
        if step_callback:
            # Truncate response for display
            response_preview = str(api_response)[:500] + "..." if len(str(api_response)) > 500 else str(api_response)
            # API calls don't use LLM tokens, just network/processing
            step_callback("API Response", f"{response_preview}|||0")
        
        # Step 3: Summarize the response
        summarizer = kernel.get_function("summarizer", "Summarizer")
        summary = await kernel.invoke(
            summarizer,
            KernelArguments(
                question=user_query,
                apiResponse=str(api_response)
            )
        )
        
        final_response = str(summary)
        
        # Track tokens for summarization - this is another major LLM call
        summary_prompt_content = f"Du bist ein präziser Assistent für Microsoft Graph API Abfragen.\n\nOriginalfrage: {user_query}\nAPI-Antwort: {str(api_response)}\n\nWICHTIG: Beantworte NUR die gestellte Frage. Sei KURZ und PRÄZISE.\n\nRegeln:\n- Bei \"Wie viele...?\": Antworte nur mit der Zahl (z.B. \"18 Benutzer\")\n- Bei \"Aktivitätsfragen: Nenne Benutzer, Aktion und App/Service\n- Bei \"was hat er gemacht\": Liste die wichtigsten Aktionen auf\n- Bei Fehlern: Erkläre kurz das Problem\n- KEINE unnötigen Details oder lange Listen"
        summary_prompt_tokens = estimate_tokens(summary_prompt_content)
        summary_response_tokens = estimate_tokens(final_response)
        summary_total_tokens = summary_prompt_tokens + summary_response_tokens
        total_tokens += summary_total_tokens
        
        if step_callback:
            step_callback("Summarization", f"Antwort erstellt|||{summary_total_tokens}")
        
        if step_callback:
            step_callback("Token Count", f"Gesamt: {total_tokens} tokens|||{total_tokens}")
        
        return final_response
        
    except Exception as e:
        return f"❌ Fehler bei der Verarbeitung: {str(e)}"


async def process_app_permissions_query(kernel: Kernel, user_query: str, step_callback=None, total_tokens: int = 0) -> str:
    """
    Multi-query approach for app permissions like Lokka
    1. Query /applications for app info
    2. Query /servicePrincipals for permission name mappings
    3. Translate GUIDs to human-readable names
    """
    
    try:
        # Extract app name from query
        app_name = extract_app_name_from_query(user_query)
        print(f"DEBUG Multi-Query: Extracted app_name: '{app_name}' from query: '{user_query}'")
        
        if not app_name:
            return "❌ Konnte den App-Namen aus der Anfrage nicht extrahieren."
        
        if step_callback:
            step_callback("Multi-Query Analysis", f"Analysiere App: {app_name}|||0")
        
        # Step 1: Get application details
        graph_request = kernel.get_function("GraphAPIRequest", "execute_graph_request")
        # Try exact match first, then contains match if exact fails
        app_query = f"/applications?$filter=displayName eq '{app_name}'&$select=requiredResourceAccess,displayName,id,appId"
        
        if step_callback:
            step_callback("Query 1/3", f"App-Details abrufen: {app_query}|||0")
        
        app_response = await kernel.invoke(
            graph_request,
            KernelArguments(
                api_path=app_query,
                method="GET",
                fetch_all=False,
                consistency_level=None,
                query_params={},
                body={}
            )
        )
        
        # Parse app response
        try:
            print(f"DEBUG Multi-Query: Raw app response: {str(app_response)[:500]}")
            
            # Handle the wrapped response format from our simplified skill
            response_str = str(app_response)
            if "Result for Graph API v1.0" in response_str:
                # Extract JSON from our formatted response
                json_start = response_str.find('{')
                if json_start > 0:
                    json_content = response_str[json_start:]
                    app_data = json.loads(json_content)
                else:
                    return f"❌ Keine JSON-Daten in der App-Response gefunden."
            else:
                app_data = json.loads(response_str)
            
            print(f"DEBUG Multi-Query: Parsed app_data keys: {list(app_data.keys()) if isinstance(app_data, dict) else 'Not a dict'}")
            
            if "value" not in app_data or not app_data["value"]:
                return f"❌ App '{app_name}' nicht gefunden. (Gefundene Keys: {list(app_data.keys()) if isinstance(app_data, dict) else 'Keine'})"
            
            app_info = app_data["value"][0]
            required_resource_access = app_info.get("requiredResourceAccess", [])
            
            print(f"DEBUG Multi-Query: App gefunden: {app_info.get('displayName')}, Berechtigungen: {len(required_resource_access)}")
            
            if not required_resource_access:
                return f"✅ Die App '{app_name}' hat keine spezifischen API-Berechtigungen konfiguriert."
            
        except Exception as e:
            return f"❌ Fehler beim Parsen der App-Daten: {str(e)}. Raw response: {str(app_response)[:200]}"
        
        # Step 2: Get Microsoft Graph ServicePrincipal for permission name mapping
        if step_callback:
            step_callback("Query 2/3", "Microsoft Graph ServicePrincipal abrufen|||0")
        
        graph_sp_query = "/servicePrincipals?$filter=appId eq '00000003-0000-0000-c000-000000000000'&$select=id,displayName,appRoles,oauth2PermissionScopes"
        
        graph_sp_response = await kernel.invoke(
            graph_request,
            KernelArguments(
                api_path=graph_sp_query,
                method="GET",
                fetch_all=False,
                consistency_level=None,
                query_params={},
                body={}
            )
        )
        
        # Parse ServicePrincipal response
        try:
            print(f"DEBUG Multi-Query: Raw SP response: {str(graph_sp_response)[:500]}")
            
            # Handle the wrapped response format from our simplified skill
            sp_response_str = str(graph_sp_response)
            if "Result for Graph API v1.0" in sp_response_str:
                # Extract JSON from our formatted response
                json_start = sp_response_str.find('{')
                if json_start > 0:
                    json_content = sp_response_str[json_start:]
                    sp_data = json.loads(json_content)
                else:
                    return f"❌ Keine JSON-Daten in der ServicePrincipal-Response gefunden."
            else:
                sp_data = json.loads(sp_response_str)
            
            print(f"DEBUG Multi-Query: Parsed sp_data keys: {list(sp_data.keys()) if isinstance(sp_data, dict) else 'Not a dict'}")
            
            if "value" not in sp_data or not sp_data["value"]:
                return "❌ Microsoft Graph ServicePrincipal nicht gefunden."
            
            graph_sp = sp_data["value"][0]
            app_roles = graph_sp.get("appRoles", [])
            oauth2_scopes = graph_sp.get("oauth2PermissionScopes", [])
            
            print(f"DEBUG Multi-Query: Found {len(app_roles)} app roles and {len(oauth2_scopes)} OAuth2 scopes")
            
            # Build permission mapping
            permission_mapping = {}
            for role in app_roles:
                permission_mapping[role.get("id")] = {
                    "name": role.get("value"),
                    "displayName": role.get("displayName"),
                    "type": "Application"
                }
            
            for scope in oauth2_scopes:
                permission_mapping[scope.get("id")] = {
                    "name": scope.get("value"),
                    "displayName": scope.get("displayName"),
                    "type": "Delegated"
                }
                
        except Exception as e:
            return f"❌ Fehler beim Parsen der ServicePrincipal-Daten: {str(e)}. Raw SP response: {str(graph_sp_response)[:200]}"
        
        # Step 3: Translate permissions to human-readable names
        if step_callback:
            step_callback("Query 3/3", "Berechtigungen übersetzen|||0")
        
        translated_permissions = []
        for resource in required_resource_access:
            resource_id = resource.get("resourceAppId")
            resource_access = resource.get("resourceAccess", [])
            
            if resource_id == "00000003-0000-0000-c000-000000000000":  # Microsoft Graph
                api_name = "Microsoft Graph"
                for access in resource_access:
                    permission_id = access.get("id")
                    permission_type = "Application" if access.get("type") == "Role" else "Delegated"
                    
                    if permission_id in permission_mapping:
                        perm_info = permission_mapping[permission_id]
                        translated_permissions.append({
                            "api": api_name,
                            "permission": perm_info["name"],
                            "displayName": perm_info["displayName"],
                            "type": permission_type,
                            "id": permission_id
                        })
                    else:
                        translated_permissions.append({
                            "api": api_name,
                            "permission": f"Unknown ({permission_id})",
                            "displayName": "Unbekannte Berechtigung",
                            "type": permission_type,
                            "id": permission_id
                        })
            else:
                # Other APIs - would need additional ServicePrincipal queries
                translated_permissions.append({
                    "api": f"Unknown API ({resource_id})",
                    "permission": "Weitere API-Abfrage erforderlich",
                    "displayName": "Weitere API-Abfrage erforderlich",
                    "type": "Unknown",
                    "id": resource_id
                })
        
        # Format response like Lokka
        result = f"🔍 Berechtigungsanalyse für App '{app_name}':\n\n"
        result += f"📋 **Konfigurierte Berechtigungen ({len(translated_permissions)}):**\n\n"
        
        app_perms = [p for p in translated_permissions if p["type"] == "Application"]
        delegated_perms = [p for p in translated_permissions if p["type"] == "Delegated"]
        
        if app_perms:
            result += "**App-Berechtigungen (Application):**\n\n"
            for perm in app_perms:
                result += f"- {perm['permission']} - {perm['displayName']}\n"
            result += "\n"
        
        if delegated_perms:
            result += "**Delegierte Berechtigungen (Delegated):**\n\n"
            for perm in delegated_perms:
                result += f"- {perm['permission']} - {perm['displayName']}\n"
            result += "\n"
        
        result += f"✅ **Analyse abgeschlossen** - {len(app_perms)} App-Berechtigungen, {len(delegated_perms)} delegierte Berechtigungen"
        
        return result
        
    except Exception as e:
        return f"❌ Fehler bei der Multi-Query-Analyse: {str(e)}"


def extract_app_name_from_query(query: str) -> str:
    """Extract app name from user query"""
    query_lower = query.lower()
    
    # Look for patterns like "app registrierung X", "rechte der app X", etc.
    import re
    
    # Pattern: "app registrierung [name]"
    match = re.search(r'app\s+registrierung\s+([^auf]+)', query_lower)
    if match:
        return match.group(1).strip()
    
    # Pattern: "rechte der app [name]" or "berechtigungen der app [name]"
    match = re.search(r'(?:rechte|berechtigungen)\s+der\s+app\s+([^auf]+)', query_lower)
    if match:
        return match.group(1).strip()
    
    # Pattern: "app [name]"
    match = re.search(r'app\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s+auf|$)', query_lower)
    if match:
        return match.group(1).strip()
    
    # Fallback: look for quoted strings
    match = re.search(r'[\'"]([^\'\"]+)[\'"]', query)
    if match:
        return match.group(1).strip()
    
    return None