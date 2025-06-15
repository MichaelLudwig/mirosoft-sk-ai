from semantic_kernel.functions.kernel_function_decorator import kernel_function
import aiohttp
from azure.identity.aio import ClientSecretCredential
import json
import logging
from datetime import datetime


class GraphAPIRequestSkill:
    """Native skill for executing Microsoft Graph API requests"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self._credential = None
        self.logger = logging.getLogger(__name__)
        self.request_history = []
    
    async def _get_access_token(self) -> str:
        """Get access token for Microsoft Graph API"""
        if not self._credential:
            self._credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        token = await self._credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    
    @kernel_function(
        description="Execute a Microsoft Graph API request",
        name="execute_graph_request"
    )
    def get_last_request_log(self) -> dict:
        """Get the last request log for debugging"""
        return self.request_history[-1] if self.request_history else {}
    
    @kernel_function(
        description="Execute a Microsoft Graph API request",
        name="execute_graph_request"
    )
    async def execute_graph_request(self, api_path: str) -> str:
        """
        Execute a Graph API request and return the response
        """
        # Ensure path starts with /
        if not api_path.startswith("/"):
            api_path = "/" + api_path
        
        # Build full URL
        full_url = self.graph_base_url + api_path
        
        # Get access token
        token = await self._get_access_token()
        
        # Make request
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Add special header for $count requests
        if "$count" in api_path:
            headers["ConsistencyLevel"] = "eventual"
        
        async with aiohttp.ClientSession() as session:
            try:
                # Log request
                request_log = {
                    "timestamp": datetime.now().isoformat(),
                    "method": "GET",
                    "url": full_url,
                    "headers": {k: "***" if k == "Authorization" else v for k, v in headers.items()}
                }
                
                async with session.get(full_url, headers=headers) as response:
                    # Log response
                    response_text = await response.text()
                    
                    request_log.update({
                        "status_code": response.status,
                        "response_headers": dict(response.headers),
                        "response_body": response_text[:1000] + "..." if len(response_text) > 1000 else response_text
                    })
                    
                    self.request_history.append(request_log)
                    self.logger.info(f"Graph API Request: {response.status} {full_url}")
                    
                    if response.status >= 400:
                        error_details = {
                            "error": f"{response.status} {response.reason}",
                            "url": full_url,
                            "status_code": response.status,
                            "response_body": response_text,
                            "message": "Graph API request failed"
                        }
                        return json.dumps(error_details, indent=2)
                    
                    # Handle $count endpoints that return plain text
                    if "$count" in api_path:
                        return json.dumps({
                            "count": int(response_text.strip()),
                            "message": f"Total count: {response_text.strip()}"
                        }, indent=2)
                    else:
                        # Regular JSON response
                        try:
                            data = json.loads(response_text)
                            return json.dumps(data, indent=2)
                        except json.JSONDecodeError:
                            return json.dumps({
                                "error": "Invalid JSON response",
                                "response_text": response_text
                            }, indent=2)
                    
            except Exception as e:
                error_log = {
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "url": full_url,
                    "exception_type": type(e).__name__
                }
                self.request_history.append(error_log)
                self.logger.error(f"Graph API Error: {str(e)}")
                
                return json.dumps({
                    "error": str(e),
                    "status_code": None,
                    "message": "Failed to execute Graph API request"
                })