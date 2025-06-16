from semantic_kernel.functions.kernel_function_decorator import kernel_function
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
import json
import logging
from datetime import datetime
from msgraph.generated.models.o_data_errors.o_data_error import ODataError


class GraphAPIRequestSkill:
    """Simplified Graph API skill following Lokka's approach"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.logger = logging.getLogger(__name__)
        
        # Initialize Graph Service Client (like Lokka)
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        self.graph_client = GraphServiceClient(
            credentials=credential,
            scopes=["https://graph.microsoft.com/.default"]
        )
    
    @kernel_function(
        description="Execute Microsoft Graph API requests with Lokka-style simplicity",
        name="execute_graph_request"
    )
    async def execute_graph_request(
        self, 
        api_path: str, 
        method: str = "GET",
        fetch_all: bool = False, 
        consistency_level: str = None,
        query_params: dict = None,
        body: dict = None
    ) -> str:
        """
        Execute Graph API request using Microsoft Graph SDK (Lokka-style)
        
        Args:
            api_path: API path (e.g., '/users', '/applications')
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            fetch_all: Auto-fetch all pages for list results
            consistency_level: ConsistencyLevel header (use 'eventual' for advanced queries)
            query_params: Query parameters dict
            body: Request body for POST/PUT/PATCH
        """
        self.logger.info(f"Graph API: {method} {api_path}")
        print(f"DEBUG: execute_graph_request called with api_path={api_path}, method={method}, fetch_all={fetch_all}, consistency_level={consistency_level}")
        
        try:
            # Clean path (remove leading slash like Lokka)
            clean_path = api_path.lstrip('/')
            
            # Parse query parameters from URL if present in path
            if '?' in clean_path:
                clean_path, query_string = clean_path.split('?', 1)
                parsed_params = {}
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        parsed_params[key] = value.replace('%20', ' ').replace("'", "'")
                # Merge with provided query_params
                if query_params:
                    parsed_params.update(query_params)
                query_params = parsed_params
            
            # Python SDK doesn't have flexible api() method like JS SDK
            # Use direct endpoint routing (simplified Lokka approach)
            response_data = await self._execute_graph_request(
                clean_path, method.upper(), query_params, body, consistency_level, fetch_all
            )
            
            # Format result (like Lokka's text formatting)
            result_text = f"Result for Graph API v1.0 - {method} {api_path}:\n\n"
            result_text += json.dumps(response_data, indent=2, default=str)
            
            # Add pagination note for single page GET (like Lokka)
            if not fetch_all and method == 'GET' and response_data:
                if hasattr(response_data, 'odata_next_link') and response_data.odata_next_link:
                    result_text += "\n\nNote: More results available. Use fetch_all=true to retrieve all pages."
            
            return result_text
            
        except ODataError as e:
            # Handle Graph errors (like Lokka's error handling)
            error_info = {
                "error": str(e.error.message) if e.error else str(e),
                "statusCode": e.response_status_code if hasattr(e, 'response_status_code') else 'N/A',
                "errorBody": str(e.error) if e.error else 'N/A',
                "attemptedPath": api_path
            }
            
            self.logger.error(f"Graph API Error: {error_info}")
            return json.dumps(error_info, indent=2)
            
        except Exception as e:
            # General error handling (like Lokka)
            error_info = {
                "error": str(e),
                "statusCode": 'N/A',
                "errorBody": 'N/A', 
                "attemptedPath": api_path
            }
            
            self.logger.error(f"Graph API Error: {error_info}")
            return json.dumps(error_info, indent=2)
    
    async def _execute_graph_request(self, path: str, method: str, query_params: dict, body: dict, consistency_level: str, fetch_all: bool):
        """Execute Graph request with endpoint routing (Lokka-style but adapted for Python SDK)"""
        
        print(f"DEBUG: _execute_graph_request called with path='{path}', method='{method}'")
        
        # Parse path to determine endpoint
        if path.startswith('users'):
            print(f"DEBUG: Routing to users handler for path: {path}")
            return await self._handle_users_request(path, method, query_params, consistency_level, fetch_all)
        elif path.startswith('applications'):
            return await self._handle_applications_request(path, method, query_params, consistency_level, fetch_all)
        elif path.startswith('servicePrincipals'):
            return await self._handle_service_principals_request(path, method, query_params, consistency_level, fetch_all)
        elif path.startswith('groups'):
            return await self._handle_groups_request(path, method, query_params, consistency_level, fetch_all)
        elif 'conditionalAccess' in path:
            return await self._handle_conditional_access_request(path, method, query_params, consistency_level, fetch_all)
        else:
            # Fallback to REST request (like Lokka for unsupported endpoints)
            return await self._fallback_rest_request(path, method, query_params, body, consistency_level)
    
    async def _handle_users_request(self, path: str, method: str, query_params: dict, consistency_level: str, fetch_all: bool):
        """Handle users endpoint requests"""
        if method != 'GET':
            raise ValueError(f"Method {method} not supported for users endpoint")
        
        if path == 'users/$count':
            print(f"DEBUG: Detected users count request, using REST fallback")
            # Special count request - use REST fallback
            return await self._fallback_rest_request(path, method, query_params, None, consistency_level)
        
        # Regular users request
        users_response = await self.graph_client.users.get()
        
        if fetch_all and users_response:
            # Fetch all pages
            all_users = list(users_response.value) if users_response.value else []
            
            while users_response.odata_next_link:
                users_response = await self.graph_client.users.with_url(users_response.odata_next_link).get()
                if users_response and users_response.value:
                    all_users.extend(users_response.value)
            
            return {
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users",
                "value": [self._serialize_user(user) for user in all_users]
            }
        else:
            # Single page
            return {
                "@odata.context": users_response.odata_context if users_response else None,
                "value": [self._serialize_user(user) for user in (users_response.value or [])]
            }
    
    async def _handle_applications_request(self, path: str, method: str, query_params: dict, consistency_level: str, fetch_all: bool):
        """Handle applications endpoint requests"""
        if method != 'GET':
            raise ValueError(f"Method {method} not supported for applications endpoint")
        
        # Like Lokka: Just pass through to Graph API, let the LLM do the business logic
        return await self._fallback_rest_request(path, method, query_params, None, consistency_level)
    
    async def _handle_service_principals_request(self, path: str, method: str, query_params: dict, consistency_level: str, fetch_all: bool):
        """Handle servicePrincipals endpoint requests"""
        if method != 'GET':
            raise ValueError(f"Method {method} not supported for servicePrincipals endpoint")
        
        return await self._fallback_rest_request(path, method, query_params, None, consistency_level)
    
    async def _handle_groups_request(self, path: str, method: str, query_params: dict, consistency_level: str, fetch_all: bool):
        """Handle groups endpoint requests"""
        if method != 'GET':
            raise ValueError(f"Method {method} not supported for groups endpoint")
        
        groups_response = await self.graph_client.groups.get()
        
        return {
            "@odata.context": groups_response.odata_context if groups_response else None,
            "value": [self._serialize_group(group) for group in (groups_response.value or [])]
        }
    
    async def _handle_conditional_access_request(self, path: str, method: str, query_params: dict, consistency_level: str, fetch_all: bool):
        """Handle conditional access requests"""
        if method != 'GET':
            raise ValueError(f"Method {method} not supported for conditional access endpoint")
        
        ca_response = await self.graph_client.identity.conditional_access.policies.get()
        
        if ca_response and ca_response.value:
            return {
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies",
                "value": [self._serialize_ca_policy(policy) for policy in ca_response.value]
            }
        else:
            return {
                "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies",
                "value": []
            }
    
    async def _fallback_rest_request(self, path: str, method: str, query_params: dict, body: dict, consistency_level: str):
        """Fallback to REST request for complex queries"""
        print(f"DEBUG: _fallback_rest_request called with path='{path}', method='{method}', query_params={query_params}, consistency_level='{consistency_level}'")
        
        # Build URL
        url = f"https://graph.microsoft.com/v1.0/{path}"
        print(f"DEBUG: Base URL: {url}")
        
        # Add query parameters
        if query_params:
            params = "&".join([f"{k}={v}" for k, v in query_params.items()])
            url += f"?{params}" if '?' not in url else f"&{params}"
            print(f"DEBUG: URL with params: {url}")
        
        # Get access token using our stored credential
        from azure.identity import ClientSecretCredential
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        token_result = credential.get_token("https://graph.microsoft.com/.default")
        
        # Make REST request
        import aiohttp
        headers = {
            "Authorization": f"Bearer {token_result.token}"
        }
        
        # Only add Content-Type for POST/PUT/PATCH requests
        if method.upper() in ["POST", "PUT", "PATCH"]:
            headers["Content-Type"] = "application/json"
        
        # For $count endpoints, always add ConsistencyLevel header
        if path.endswith('$count'):
            headers["ConsistencyLevel"] = "eventual"
            print(f"DEBUG: Added ConsistencyLevel header for $count endpoint: {headers['ConsistencyLevel']}")
        elif consistency_level and consistency_level != 'None':
            headers["ConsistencyLevel"] = consistency_level
            print(f"DEBUG: Added ConsistencyLevel header from parameter: {headers['ConsistencyLevel']}")
        
        print(f"DEBUG: Final headers: {headers}")
        print(f"DEBUG: Making {method} request to: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=body) as response:
                print(f"DEBUG: Response status: {response.status}")
                response_text = await response.text()
                print(f"DEBUG: Response text (first 200 chars): {response_text[:200]}")
                
                if response.status >= 400:
                    print(f"DEBUG: Error response - status: {response.status}, reason: {response.reason}")
                    return {
                        "error": f"REST request failed: {response.status} {response.reason}",
                        "response_body": response_text,
                        "url": url
                    }
                
                try:
                    result = json.loads(response_text) if response_text else {}
                    print(f"DEBUG: Successfully parsed JSON response")
                    return result
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON decode error: {e}")
                    return {"raw_response": response_text, "url": url}
    
    def _serialize_user(self, user) -> dict:
        """Serialize user object"""
        return {
            "id": getattr(user, 'id', None),
            "displayName": getattr(user, 'display_name', None),
            "userPrincipalName": getattr(user, 'user_principal_name', None),
            "mail": getattr(user, 'mail', None),
            "accountEnabled": getattr(user, 'account_enabled', None)
        }
    
    def _serialize_group(self, group) -> dict:
        """Serialize group object"""
        return {
            "id": getattr(group, 'id', None),
            "displayName": getattr(group, 'display_name', None),
            "description": getattr(group, 'description', None),
            "groupTypes": getattr(group, 'group_types', None)
        }
    
    def _serialize_ca_policy(self, policy) -> dict:
        """Serialize conditional access policy"""
        return {
            "id": getattr(policy, 'id', None),
            "displayName": getattr(policy, 'display_name', None),
            "state": getattr(policy, 'state', None),
            "createdDateTime": getattr(policy, 'created_date_time', None)
        }
    
    async def _fetch_all_pages(self, request):
        """Fetch all pages like Lokka's PageIterator approach"""
        try:
            # Get first page
            first_response = await request.get()
            
            # If no pagination, return as-is
            if not hasattr(first_response, 'value') or not hasattr(first_response, 'odata_next_link'):
                return first_response
            
            # Collect all items
            all_items = list(first_response.value) if first_response.value else []
            odata_context = first_response.odata_context if hasattr(first_response, 'odata_context') else None
            
            # Follow pagination links
            next_link = first_response.odata_next_link
            while next_link:
                next_response = await self.graph_client.api(next_link).get()
                
                if hasattr(next_response, 'value') and next_response.value:
                    all_items.extend(next_response.value)
                
                next_link = next_response.odata_next_link if hasattr(next_response, 'odata_next_link') else None
            
            # Return combined result (like Lokka)
            return {
                '@odata.context': odata_context,
                'value': all_items
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching all pages: {e}")
            # Fallback to first page only
            return await request.get()