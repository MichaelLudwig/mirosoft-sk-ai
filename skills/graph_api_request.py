from semantic_kernel.functions.kernel_function_decorator import kernel_function
import aiohttp
from azure.identity.aio import ClientSecretCredential
import json


class GraphAPIRequestSkill:
    """Native skill for executing Microsoft Graph API requests"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self._credential = None
    
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
                async with session.get(full_url, headers=headers) as response:
                    response.raise_for_status()
                    
                    # Handle $count endpoints that return plain text
                    if "$count" in api_path:
                        count_text = await response.text()
                        return json.dumps({
                            "count": int(count_text.strip()),
                            "message": f"Total count: {count_text.strip()}"
                        }, indent=2)
                    else:
                        # Regular JSON response
                        data = await response.json()
                        return json.dumps(data, indent=2)
                    
            except aiohttp.ClientError as e:
                return json.dumps({
                    "error": str(e),
                    "status_code": response.status if 'response' in locals() else None,
                    "message": "Failed to execute Graph API request"
                })