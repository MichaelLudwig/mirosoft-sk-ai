from semantic_kernel.functions.kernel_function_decorator import kernel_function
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
import json
import logging
from datetime import datetime
from msgraph.generated.models.o_data_errors.o_data_error import ODataError


class GraphAPIRequestSkill:
    """Enhanced native skill for executing Microsoft Graph API requests using the official SDK"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.logger = logging.getLogger(__name__)
        self.request_history = []
        
        # Initialize Azure Credential (synchronous version for SDK)
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Initialize Graph Service Client
        self.graph_client = GraphServiceClient(
            credentials=self._credential,
            scopes=["https://graph.microsoft.com/.default"]
        )
    
    @kernel_function(
        description="Execute a Microsoft Graph API request using the official SDK",
        name="execute_graph_request"
    )
    async def execute_graph_request(self, api_path: str, fetch_all: bool = False, consistency_level: str = None) -> str:
        """
        Execute a Graph API request using the Microsoft Graph SDK
        
        Args:
            api_path: The API path (e.g., '/users', '/identity/conditionalAccess/policies')
            fetch_all: Whether to automatically fetch all pages (default: False)
            consistency_level: ConsistencyLevel header value (default: None, but 'eventual' for advanced queries)
        """
        self.logger.info(f"Executing Graph API request: {api_path}, fetch_all={fetch_all}, consistency_level={consistency_level}")
        
        try:
            # Remove leading slash for SDK
            if api_path.startswith("/"):
                api_path = api_path[1:]
            
            # Auto-detect need for ConsistencyLevel header
            needs_consistency = (
                "$count" in api_path or 
                "$filter" in api_path or 
                "$search" in api_path or 
                "$orderby" in api_path or
                "conditionalAccess" in api_path
            )
            
            if needs_consistency and not consistency_level:
                consistency_level = "eventual"
                self.logger.info(f"Auto-setting ConsistencyLevel to 'eventual' for advanced query: {api_path}")
            
            # Log request details
            request_log = {
                "timestamp": datetime.now().isoformat(),
                "method": "GET",
                "api_path": api_path,
                "fetch_all": fetch_all,
                "consistency_level": consistency_level,
                "sdk_version": "msgraph-sdk"
            }
            
            # Build request using Graph SDK
            # Start with the client and navigate to the correct endpoint
            if api_path == "users/$count":
                # Special handling for user count - use REST fallback for simplicity
                headers = {}
                if consistency_level:
                    headers["ConsistencyLevel"] = consistency_level
                
                # Get access token
                token_result = await self._credential.get_token("https://graph.microsoft.com/.default")
                
                # Make direct REST call
                import aiohttp
                request_headers = {
                    "Authorization": f"Bearer {token_result.token}",
                    "Content-Type": "application/json"
                }
                request_headers.update(headers)
                
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://graph.microsoft.com/v1.0/users/$count", headers=request_headers) as response:
                        if response.status == 200:
                            count_value = int(await response.text())
                            result = {
                                "count": count_value,
                                "message": f"Total count: {count_value}"
                            }
                        else:
                            error_text = await response.text()
                            result = {
                                "error": f"Count request failed: {response.status}",
                                "details": error_text
                            }
                
            elif api_path.startswith("users"):
                # Users endpoint
                if fetch_all:
                    # Fetch all users with pagination
                    all_users = []
                    users_response = await self.graph_client.users.get()
                    
                    if users_response and users_response.value:
                        all_users.extend(users_response.value)
                        
                        # Handle pagination
                        while users_response.odata_next_link:
                            users_response = await self.graph_client.users.with_url(
                                users_response.odata_next_link
                            ).get()
                            if users_response and users_response.value:
                                all_users.extend(users_response.value)
                    
                    result = {
                        "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#users",
                        "value": [self._serialize_user(user) for user in all_users]
                    }
                else:
                    # Single page
                    users_response = await self.graph_client.users.get()
                    result = {
                        "@odata.context": users_response.odata_context if users_response else None,
                        "value": [self._serialize_user(user) for user in (users_response.value or [])]
                    }
                    if users_response and users_response.odata_next_link:
                        result["@odata.nextLink"] = users_response.odata_next_link
                        
            elif "conditionalAccess/policies" in api_path:
                # Conditional Access Policies - simple approach
                try:
                    # Use the conditional access policies endpoint directly
                    ca_response = await self.graph_client.identity.conditional_access.policies.get()
                    self.logger.info(f"CA Response type: {type(ca_response)}")
                    self.logger.info(f"CA Response attributes: {dir(ca_response) if ca_response else 'None'}")
                    
                    if ca_response:
                        # Check for different possible attribute names
                        policies = None
                        odata_context = None
                        
                        # Try different attribute variations
                        if hasattr(ca_response, 'value'):
                            policies = ca_response.value
                        elif hasattr(ca_response, 'policies'):
                            policies = ca_response.policies
                        elif isinstance(ca_response, list):
                            policies = ca_response
                        
                        # Try different context attribute names
                        if hasattr(ca_response, 'odata_context'):
                            odata_context = ca_response.odata_context
                        elif hasattr(ca_response, '@odata.context'):
                            odata_context = getattr(ca_response, '@odata.context')
                        
                        if policies:
                            result = {
                                "@odata.context": odata_context or f"https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies",
                                "value": [self._serialize_ca_policy(policy) for policy in policies],
                                "count": len(policies)
                            }
                        else:
                            result = {
                                "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies",
                                "value": [],
                                "message": "No conditional access policies found",
                                "debug_info": f"Response type: {type(ca_response)}, attributes: {list(vars(ca_response).keys()) if hasattr(ca_response, '__dict__') else 'No dict'}"
                            }
                    else:
                        result = {
                            "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#identity/conditionalAccess/policies",
                            "value": [],
                            "message": "No response received"
                        }
                        
                except Exception as ca_error:
                    self.logger.error(f"Conditional Access error: {ca_error}")
                    # Fallback to simple result
                    result = {
                        "error": f"Conditional Access query failed: {str(ca_error)}",
                        "message": "CA policies require proper permissions",
                        "suggestion": "Check if the app has Policy.Read.All permission"
                    }
                
            elif api_path.startswith("directoryRoles"):
                # Directory Roles
                roles_response = await self.graph_client.directory_roles.get()
                result = {
                    "@odata.context": roles_response.odata_context if roles_response else None,
                    "value": [self._serialize_directory_role(role) for role in (roles_response.value or [])]
                }
                
            else:
                # Generic fallback - try to parse the path and build request
                result = await self._handle_generic_request(api_path, consistency_level)
            
            # Update request log
            request_log.update({
                "status_code": 200,
                "response_items": len(result.get("value", [])) if isinstance(result.get("value"), list) else 1
            })
            self.request_history.append(request_log)
            
            # Return formatted JSON
            return json.dumps(result, indent=2, default=str)
            
        except ODataError as e:
            # Handle Graph SDK specific errors
            error_details = {
                "error": str(e.error.message) if e.error else str(e),
                "status_code": e.response_status_code if hasattr(e, 'response_status_code') else None,
                "error_code": e.error.code if e.error else None,
                "message": "Microsoft Graph API error",
                "api_path": api_path
            }
            
            request_log.update({
                "status_code": error_details["status_code"],
                "error": error_details["error"]
            })
            self.request_history.append(request_log)
            self.logger.error(f"Graph API OData Error: {error_details}")
            
            return json.dumps(error_details, indent=2)
            
        except Exception as e:
            # Handle general errors
            error_details = {
                "error": str(e),
                "status_code": None,
                "message": "Failed to execute Graph API request",
                "exception_type": type(e).__name__,
                "api_path": api_path
            }
            
            request_log.update({
                "status_code": None,
                "error": str(e)
            })
            self.request_history.append(request_log)
            self.logger.error(f"Graph API Error: {str(e)}")
            
            return json.dumps(error_details, indent=2)
    
    def _serialize_user(self, user) -> dict:
        """Serialize a User object to dictionary"""
        if not user:
            return {}
        return {
            "id": user.id,
            "displayName": user.display_name,
            "userPrincipalName": user.user_principal_name,
            "mail": user.mail,
            "accountEnabled": user.account_enabled,
            "createdDateTime": user.created_date_time.isoformat() if user.created_date_time else None
        }
    
    def _serialize_ca_policy(self, policy) -> dict:
        """Serialize a Conditional Access Policy object to dictionary"""
        if not policy:
            return {}
        
        # Extract basic info safely
        result = {}
        
        try:
            result["id"] = getattr(policy, 'id', None)
            result["displayName"] = getattr(policy, 'display_name', None)
            
            # Handle state attribute safely
            state = getattr(policy, 'state', None)
            if state:
                if hasattr(state, 'value'):
                    result["state"] = state.value
                else:
                    result["state"] = str(state)
            else:
                result["state"] = "unknown"
            
            # Handle datetime attributes safely
            created = getattr(policy, 'created_date_time', None)
            if created:
                result["createdDateTime"] = created.isoformat() if hasattr(created, 'isoformat') else str(created)
            
            modified = getattr(policy, 'modified_date_time', None)
            if modified:
                result["modifiedDateTime"] = modified.isoformat() if hasattr(modified, 'isoformat') else str(modified)
            
            # Add debug info about available attributes
            result["debug_attributes"] = list(vars(policy).keys()) if hasattr(policy, '__dict__') else dir(policy)
            
        except Exception as e:
            self.logger.error(f"Error serializing CA policy: {e}")
            result = {
                "error": f"Serialization failed: {str(e)}",
                "policy_type": str(type(policy)),
                "available_attributes": dir(policy) if policy else []
            }
        
        return result
    
    def _serialize_directory_role(self, role) -> dict:
        """Serialize a Directory Role object to dictionary"""
        if not role:
            return {}
        return {
            "id": role.id,
            "displayName": role.display_name,
            "description": role.description,
            "roleTemplateId": role.role_template_id
        }
    
    async def _handle_generic_request(self, api_path: str, consistency_level: str = None) -> dict:
        """Handle generic API requests by parsing the path and routing to appropriate SDK methods"""
        try:
            self.logger.info(f"Generic request for: {api_path}")
            
            # Parse the API path to determine the endpoint
            if api_path.startswith("applications"):
                return await self._handle_applications_request(api_path, consistency_level)
            elif api_path.startswith("servicePrincipals"):
                return await self._handle_service_principals_request(api_path, consistency_level)
            elif api_path.startswith("groups"):
                return await self._handle_groups_request(api_path, consistency_level)
            else:
                # Fallback to REST call for unsupported endpoints
                return await self._fallback_rest_request(api_path, consistency_level)
                
        except Exception as e:
            self.logger.error(f"Generic request failed for {api_path}: {e}")
            return {
                "error": f"Generic request failed: {str(e)}",
                "api_path": api_path,
                "exception_type": type(e).__name__
            }
    
    async def _handle_applications_request(self, api_path: str, consistency_level: str = None) -> dict:
        """Handle applications endpoint requests with Lokka-style comprehensive permission analysis"""
        try:
            # Parse query parameters
            if "?" in api_path:
                base_path, query_string = api_path.split("?", 1)
                params = self._parse_query_params(query_string)
            else:
                params = {}
            
            # Build the request
            request_builder = self.graph_client.applications
            
            # Apply filters and selects
            if "$filter" in params:
                # Note: Python SDK doesn't support $filter in the same way as JS
                # We'll need to get all and filter client-side for now
                apps_response = await request_builder.get()
                
                # Client-side filtering (simplified)
                if apps_response and apps_response.value:
                    filtered_apps = []
                    filter_expr = params["$filter"]
                    
                    for app in apps_response.value:
                        if self._matches_filter(app, filter_expr):
                            # Check if this is a comprehensive permissions request
                            if ("requiredResourceAccess" in params.get("$select", "") or 
                                "rechte" in api_path.lower() or 
                                "berechtigungen" in api_path.lower() or
                                "permissions" in api_path.lower()):
                                app_dict = await self._get_comprehensive_app_permissions(app)
                                self.logger.info(f"Comprehensive permissions analysis completed for app: {app_dict.get('display_name', 'Unknown')}")
                            else:
                                app_dict = self._object_to_dict(app)
                            
                            # Apply $select if specified
                            if "$select" in params:
                                selected_fields = params["$select"].split(",")
                                app_dict = {k: v for k, v in app_dict.items() if k in selected_fields or k in ["id", "display_name"]}
                            
                            filtered_apps.append(app_dict)
                    
                    return {
                        "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#applications",
                        "value": filtered_apps
                    }
                else:
                    return {
                        "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#applications",
                        "value": []
                    }
            else:
                # Get all applications
                apps_response = await request_builder.get()
                
                if apps_response and apps_response.value:
                    result = {
                        "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#applications",
                        "value": [self._object_to_dict(app) for app in apps_response.value]
                    }
                    return result
                else:
                    return {
                        "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#applications",
                        "value": []
                    }
                    
        except Exception as e:
            self.logger.error(f"Applications request failed: {e}")
            return {
                "error": f"Applications request failed: {str(e)}",
                "api_path": api_path
            }
    
    async def _handle_service_principals_request(self, api_path: str, consistency_level: str = None) -> dict:
        """Handle servicePrincipals endpoint requests"""
        try:
            # Similar to applications but for service principals
            request_builder = self.graph_client.service_principals
            sps_response = await request_builder.get()
            
            if sps_response and sps_response.value:
                result = {
                    "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#servicePrincipals",
                    "value": [self._object_to_dict(sp) for sp in sps_response.value]
                }
                return result
            else:
                return {
                    "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#servicePrincipals",
                    "value": []
                }
                
        except Exception as e:
            self.logger.error(f"Service principals request failed: {e}")
            return {
                "error": f"Service principals request failed: {str(e)}",
                "api_path": api_path
            }
    
    async def _handle_groups_request(self, api_path: str, consistency_level: str = None) -> dict:
        """Handle groups endpoint requests"""
        try:
            groups_response = await self.graph_client.groups.get()
            
            if groups_response and groups_response.value:
                result = {
                    "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#groups",
                    "value": [self._object_to_dict(group) for group in groups_response.value]
                }
                return result
            else:
                return {
                    "@odata.context": f"https://graph.microsoft.com/v1.0/$metadata#groups",
                    "value": []
                }
                
        except Exception as e:
            self.logger.error(f"Groups request failed: {e}")
            return {
                "error": f"Groups request failed: {str(e)}",
                "api_path": api_path
            }
    
    async def _fallback_rest_request(self, api_path: str, consistency_level: str = None) -> dict:
        """Fallback to REST request for endpoints not supported by SDK"""
        try:
            # Build full URL
            full_url = f"https://graph.microsoft.com/v1.0/{api_path}"
            
            # Get access token
            token_result = await self._credential.get_token("https://graph.microsoft.com/.default")
            
            # Make REST request
            import aiohttp
            headers = {
                "Authorization": f"Bearer {token_result.token}",
                "Content-Type": "application/json"
            }
            
            if consistency_level:
                headers["ConsistencyLevel"] = consistency_level
            
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=headers) as response:
                    response_text = await response.text()
                    
                    if response.status >= 400:
                        return {
                            "error": f"REST request failed: {response.status} {response.reason}",
                            "response_body": response_text,
                            "api_path": api_path
                        }
                    
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError:
                        return {
                            "raw_response": response_text,
                            "api_path": api_path
                        }
                        
        except Exception as e:
            self.logger.error(f"Fallback REST request failed: {e}")
            return {
                "error": f"Fallback REST request failed: {str(e)}",
                "api_path": api_path
            }
    
    def _parse_query_params(self, query_string: str) -> dict:
        """Parse query parameters from URL"""
        params = {}
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value.replace("%20", " ").replace("'", "'")
        return params
    
    def _matches_filter(self, obj, filter_expr: str) -> bool:
        """Simple client-side filtering (basic displayName eq support)"""
        try:
            if "displayName eq" in filter_expr:
                # Extract the value from "displayName eq 'value'"
                parts = filter_expr.split("displayName eq")
                if len(parts) > 1:
                    value = parts[1].strip().strip("'\"")
                    obj_display_name = getattr(obj, 'display_name', '')
                    return obj_display_name == value
        except:
            pass
        return False
    
    def _object_to_dict(self, obj) -> dict:
        """Convert a Graph SDK object to dictionary with deep serialization"""
        if obj is None:
            return {}
        
        result = {}
        
        try:
            # First, try to get the actual object attributes using vars()
            if hasattr(obj, '__dict__'):
                obj_vars = vars(obj)
                for attr_name, attr_value in obj_vars.items():
                    if not attr_name.startswith('_'):
                        result[attr_name] = self._serialize_value(attr_value)
            
            # Also check dir() for properties that might not be in __dict__
            for attr_name in dir(obj):
                if (not attr_name.startswith('_') and 
                    not callable(getattr(obj, attr_name, None)) and
                    attr_name not in result):
                    try:
                        attr_value = getattr(obj, attr_name)
                        result[attr_name] = self._serialize_value(attr_value)
                    except:
                        continue
            
        except Exception as e:
            self.logger.error(f"Error converting object to dict: {e}")
            result = {
                "error": f"Conversion failed: {str(e)}",
                "object_type": str(type(obj)),
                "available_attrs": dir(obj) if obj else []
            }
        
        return result
    
    def _serialize_value(self, value):
        """Recursively serialize any value to JSON-compatible format"""
        if value is None:
            return None
        elif isinstance(value, (str, int, float, bool)):
            return value
        elif hasattr(value, 'value'):  # Enum
            return value.value
        elif hasattr(value, 'isoformat'):  # DateTime
            return value.isoformat()
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif hasattr(value, '__dict__'):
            # Nested object - recurse
            return self._object_to_dict(value)
        else:
            # Convert to string as fallback
            return str(value)
    
    async def _get_comprehensive_app_permissions(self, app) -> dict:
        """Get comprehensive app permissions following Lokka's multi-query strategy"""
        try:
            app_dict = self._object_to_dict(app)
            app_id = app_dict.get('id') or app_dict.get('app_id')
            
            if not app_id:
                return app_dict
            
            self.logger.info(f"Getting comprehensive permissions for app {app_id}")
            
            # Step 1: Get basic app info (already have it)
            # Step 2: Get corresponding service principal
            service_principal = await self._get_service_principal_for_app(app_id)
            
            # Step 3: Get permission mappings
            permission_mappings = self._get_permission_mappings()
            
            # Step 4: Analyze required vs granted permissions
            comprehensive_permissions = await self._analyze_app_permissions(
                app_dict, service_principal, permission_mappings
            )
            
            # Add comprehensive permission analysis to app data
            app_dict['comprehensive_permissions'] = comprehensive_permissions
            
            return app_dict
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive permissions: {e}")
            app_dict = self._object_to_dict(app)
            app_dict['permission_analysis_error'] = str(e)
            return app_dict
    
    async def _get_service_principal_for_app(self, app_id: str) -> dict:
        """Get the service principal for an application"""
        try:
            self.logger.info(f"Looking for service principal with appId: {app_id}")
            
            # Get service principal by appId using filter (more efficient)
            url = f"servicePrincipals?$filter=appId eq '{app_id}'"
            response = await self._fallback_rest_request(url)
            
            if "value" in response and response["value"]:
                sp = response["value"][0]  # Should be unique
                self.logger.info(f"Found service principal: {sp.get('displayName', 'Unknown')} (ID: {sp.get('id', 'Unknown')})")
                return sp
            else:
                self.logger.info(f"No service principal found for appId: {app_id}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting service principal for app {app_id}: {e}")
            return None
    
    def _get_permission_mappings(self) -> dict:
        """Get permission GUID to human-readable name mappings"""
        # Microsoft Graph API permissions (most common ones)
        microsoft_graph_permissions = {
            # User permissions (from your data)
            "e1fe6dd8-ba31-4d61-89e7-88639da4683d": "User.Read",
            "b340eb25-3456-403f-be2f-af7a0d370277": "User.ReadBasic.All",
            "df021288-bdef-4463-88db-98f22de89214": "User.Read.All",
            "204e0828-b5ca-4ad8-b9f3-f32a958e7cc4": "User.ReadWrite.All",
            
            # Directory permissions (from your data)
            "7ab1d382-f21e-4acd-a863-ba3e13f7da61": "Directory.Read.All",
            "5b567255-7703-4780-807c-7be8301ae99b": "Directory.ReadWrite.All",
            "483bed4a-2ad3-4361-a73b-c83ccdbdc53c": "Directory.AccessAsUser.All",
            "06da0dbc-49e2-44d2-8312-53f166ab848a": "Directory.Read.All",
            "c5366453-9fb0-48a5-a156-24f0c49a4b84": "Directory.ReadWrite.All",
            
            # Group permissions (from your data)
            "5f8c59db-677d-491f-a6b8-5f174b11ec1d": "Group.Read.All", 
            "62a82d76-70ea-41e2-9197-370581804d09": "Group.ReadWrite.All",
            "5b567255-7703-4780-807c-7be8301ae99b": "Group.Read.All",  # Alternative ID
            "4e46008b-f24c-477d-8fff-7bb4ec7aafe0": "Group.ReadWrite.All",
            
            # Application permissions (from your data)
            "9a5d68dd-52b0-4cc2-bd40-abcf44ac3a30": "Application.Read.All",
            "1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9": "Application.Read.All",
            "1cda74f2-2616-4834-b122-5cb1b07f8a59": "Application.ReadWrite.All",
            
            # Policy permissions (from your data)
            "246dd0d5-5bd0-4def-940b-0421030a5b68": "Policy.Read.All",
            
            # Device permissions (from your data)
            "06a5fe6d-c49d-46a7-b082-56b1b14103c7": "Device.Read.All",
            "230c1aed-a721-4c5d-9cb4-a90514e508ef": "Device.Command",
            "7438b122-aefc-4978-80ed-43db9fcc7715": "Device.Read.All",
            "1138cb37-bd11-4084-a2b7-9f71582aeddb": "Device.ReadWrite.All",
            
            # Device Management (Intune) permissions (from your data)
            "dc377aa6-52d8-4e23-b271-2a7ae04cedf3": "DeviceManagementManagedDevices.Read.All",
            "b0afded3-3588-46d8-8b3d-9842eff778da": "DeviceManagementManagedDevices.ReadWrite.All",
            
            # Mail permissions
            "810c84a8-4a9e-49e6-bf7d-12d183f40d01": "Mail.Read",
            "693c5e45-0940-467d-9b8a-1022fb9d42ef": "Mail.ReadWrite",
            "75359482-378d-4052-8f01-80520e7db3cd": "Mail.Read.Shared",
            
            # Calendar permissions
            "465a38f9-76ea-45b9-9f34-9e8b0d4b0b42": "Calendars.Read",
            "1ec239c2-d7c9-4623-a91a-a9775856bb36": "Calendars.ReadWrite",
            
            # Files permissions
            "df85f4d6-205c-4ac5-a5ea-6bf408dba283": "Files.Read.All",
            "75359482-378d-4052-8f01-80520e7db3cd": "Files.ReadWrite.All",
            
            # Sites permissions
            "332a536c-c7ef-4017-ab91-336970924f0d": "Sites.Read.All",
            "9492366f-7969-46a4-8d15-ed1a20078fff": "Sites.ReadWrite.All",
            
            # Policy permissions
            "246dd0d5-5bd0-4def-940b-0421030a5b68": "Policy.Read.All",
            "40b534c3-9552-4550-901b-23879c90bcf9": "Policy.ReadWrite.ConditionalAccess",
            
            # Reports permissions
            "230c1aed-a721-4c5d-9cb4-a90514e508ef": "Reports.Read.All",
            
            # Device permissions
            "7438b122-aefc-4978-80ed-43db9fcc7715": "Device.Read.All",
            "1138cb37-bd11-4084-a2b7-9f71582aeddb": "Device.ReadWrite.All",
        }
        
        # Azure Active Directory Graph permissions (legacy, but still used)
        aad_graph_permissions = {
            "5778995a-e1bf-45b8-affa-663a9f3f4d04": "Directory.Read.All",
            "78c8a3c8-a07e-4b9e-af1b-b5ccab50a175": "Directory.ReadWrite.All",
            "824c81eb-e3f8-4ee6-8f6d-de7f50d565b7": "Application.ReadWrite.OwnedBy",
        }
        
        return {
            "00000003-0000-0000-c000-000000000000": {  # Microsoft Graph
                "name": "Microsoft Graph",
                "permissions": microsoft_graph_permissions
            },
            "00000002-0000-0000-c000-000000000000": {  # Azure Active Directory Graph
                "name": "Azure Active Directory Graph",
                "permissions": aad_graph_permissions
            }
        }
    
    async def _analyze_app_permissions(self, app_dict: dict, service_principal: dict, permission_mappings: dict) -> dict:
        """Analyze app permissions in Lokka style - required vs granted with human-readable names"""
        try:
            analysis = {
                "required_permissions": [],
                "granted_permissions": [],
                "permission_summary": {
                    "total_required": 0,
                    "total_granted": 0,
                    "apis_accessed": [],
                    "permission_types": {"application": 0, "delegated": 0}
                }
            }
            
            # Analyze required permissions from application registration
            required_resource_access = app_dict.get('required_resource_access', [])
            if required_resource_access:
                for resource in required_resource_access:
                    resource_id = resource.get('resource_app_id')
                    resource_access = resource.get('resource_access', [])
                    
                    api_info = permission_mappings.get(resource_id, {
                        "name": f"Unknown API ({resource_id})",
                        "permissions": {}
                    })
                    
                    analysis["permission_summary"]["apis_accessed"].append(api_info["name"])
                    
                    for access in resource_access:
                        permission_id = access.get('id')
                        permission_type = access.get('type')  # Role = Application, Scope = Delegated
                        
                        permission_name = api_info["permissions"].get(
                            permission_id, 
                            f"Unknown Permission ({permission_id})"
                        )
                        
                        permission_info = {
                            "api": api_info["name"],
                            "permission_id": permission_id,
                            "permission_name": permission_name,
                            "type": "Application" if permission_type == "Role" else "Delegated",
                            "granted": False  # Will be updated when checking grants
                        }
                        
                        analysis["required_permissions"].append(permission_info)
                        analysis["permission_summary"]["total_required"] += 1
                        
                        if permission_type == "Role":
                            analysis["permission_summary"]["permission_types"]["application"] += 1
                        else:
                            analysis["permission_summary"]["permission_types"]["delegated"] += 1
            
            # Check granted permissions via service principal
            if service_principal:
                sp_id = service_principal.get('id')
                if sp_id:
                    # Get app role assignments (application permissions)
                    app_role_assignments = await self._get_app_role_assignments(sp_id)
                    # Get OAuth2 permission grants (delegated permissions)
                    oauth2_grants = await self._get_oauth2_permission_grants(sp_id)
                    
                    # Match granted permissions with required permissions
                    self._match_granted_permissions(analysis, app_role_assignments, oauth2_grants, permission_mappings)
            else:
                analysis["note"] = "Service principal not found - cannot check granted permissions"
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing app permissions: {e}")
            return {
                "error": f"Permission analysis failed: {str(e)}",
                "required_permissions": [],
                "granted_permissions": []
            }
    
    async def _get_app_role_assignments(self, service_principal_id: str) -> list:
        """Get app role assignments for a service principal (application permissions)"""
        try:
            # Use REST fallback for appRoleAssignments as SDK might not have direct support
            url = f"servicePrincipals/{service_principal_id}/appRoleAssignments"
            response = await self._fallback_rest_request(url)
            
            if "value" in response:
                return response["value"]
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting app role assignments: {e}")
            return []
    
    async def _get_oauth2_permission_grants(self, service_principal_id: str) -> list:
        """Get OAuth2 permission grants for a service principal (delegated permissions)"""
        try:
            # Get OAuth2 permission grants where clientId matches our service principal
            url = f"oauth2PermissionGrants?$filter=clientId eq '{service_principal_id}'"
            response = await self._fallback_rest_request(url)
            
            if "value" in response:
                return response["value"]
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting OAuth2 permission grants: {e}")
            return []
    
    def _match_granted_permissions(self, analysis: dict, app_role_assignments: list, oauth2_grants: list, permission_mappings: dict):
        """Match granted permissions with required permissions and update analysis"""
        try:
            granted_app_permissions = set()
            granted_delegated_permissions = set()
            
            # Process app role assignments (application permissions)
            for assignment in app_role_assignments:
                resource_id = assignment.get('resourceId')
                app_role_id = assignment.get('appRoleId')
                
                if resource_id and app_role_id:
                    # Find the API this permission belongs to
                    for api_id, api_info in permission_mappings.items():
                        if app_role_id in api_info["permissions"]:
                            permission_name = api_info["permissions"][app_role_id]
                            granted_app_permissions.add((api_info["name"], permission_name, app_role_id))
                            break
            
            # Process OAuth2 permission grants (delegated permissions)
            for grant in oauth2_grants:
                resource_id = grant.get('resourceId')
                scope = grant.get('scope', '')
                
                if resource_id and scope:
                    # Scope contains space-separated permission names
                    scopes = scope.split(' ') if scope else []
                    
                    # Find the API this permission belongs to
                    for api_id, api_info in permission_mappings.items():
                        for scope_name in scopes:
                            # Look for the scope name in our permission mappings
                            for perm_id, perm_name in api_info["permissions"].items():
                                if perm_name == scope_name:
                                    granted_delegated_permissions.add((api_info["name"], perm_name, perm_id))
                                    break
            
            # Update required permissions to mark which ones are granted
            for req_perm in analysis["required_permissions"]:
                perm_id = req_perm["permission_id"]
                perm_type = req_perm["type"]
                api_name = req_perm["api"]
                perm_name = req_perm["permission_name"]
                
                if perm_type == "Application":
                    # Check if this app permission is granted
                    for granted_api, granted_name, granted_id in granted_app_permissions:
                        if granted_id == perm_id or (granted_api == api_name and granted_name == perm_name):
                            req_perm["granted"] = True
                            break
                else:  # Delegated
                    # Check if this delegated permission is granted
                    for granted_api, granted_name, granted_id in granted_delegated_permissions:
                        if granted_id == perm_id or (granted_api == api_name and granted_name == perm_name):
                            req_perm["granted"] = True
                            break
            
            # Create granted permissions list
            analysis["granted_permissions"] = []
            
            for api_name, perm_name, perm_id in granted_app_permissions:
                analysis["granted_permissions"].append({
                    "api": api_name,
                    "permission_name": perm_name,
                    "permission_id": perm_id,
                    "type": "Application",
                    "required": any(rp["permission_id"] == perm_id for rp in analysis["required_permissions"])
                })
            
            for api_name, perm_name, perm_id in granted_delegated_permissions:
                analysis["granted_permissions"].append({
                    "api": api_name,
                    "permission_name": perm_name,
                    "permission_id": perm_id,
                    "type": "Delegated",
                    "required": any(rp["permission_id"] == perm_id for rp in analysis["required_permissions"])
                })
            
            # Update summary
            analysis["permission_summary"]["total_granted"] = len(analysis["granted_permissions"])
            
        except Exception as e:
            self.logger.error(f"Error matching granted permissions: {e}")
            analysis["granted_permissions"] = []
            analysis["permission_matching_error"] = str(e)