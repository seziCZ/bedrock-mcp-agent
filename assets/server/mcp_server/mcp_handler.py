# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import json
import logging
from contextvars import ContextVar
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from fastmcp.tools.tool import ToolResult
from mcp.types import PromptMessage

from .models import (
    Capabilities,
    ErrorContent,
    ImageContent,
    InitializeResult,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    Resource,
    ResourceContent,
    ServerInfo,
    StaticResource,
    TextContent,
)
from .session import (
    DynamoDBSessionStore,
    NoOpSessionStore,
    SessionStore
)

logger = logging.getLogger(__name__)

# Context variable to store current session ID
current_session_id: ContextVar[Optional[str]] = ContextVar("current_session_id", default=None)

T = TypeVar("T")


class SessionData(Generic[T]):
    """Helper class for type-safe session data access."""

    def __init__(self, data: Dict[str, Any]):
        """Initialize the class."""
        self._data = data

    def get(self, key: str, default: T = None) -> T:
        """Get a value from session data with type safety."""
        return self._data.get(key, default)

    def set(self, key: str, value: T) -> None:
        """Set a value in session data."""
        self._data[key] = value

    def raw(self) -> Dict[str, Any]:
        """Get the raw dictionary data."""
        return self._data


class MCPLambdaHandler:
    """A class to handle MCP (Model Context Protocol) HTTP events in AWS Lambda."""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        session_store: Optional[Union[SessionStore, str]] = None,
    ):
        """Initialize the MCP handler."""
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict] = {}
        self.tool_implementations: Dict[str, Callable] = {}
        self.resources: Dict[str, Resource] = {}
        self.prompts: Dict[str, Dict] = {}
        self.prompt_implementations: Dict[str, Callable] = {}

        # Configure session storage
        if session_store is None:
            self.session_store = NoOpSessionStore()
        elif isinstance(session_store, str):
            self.session_store = DynamoDBSessionStore(table_name=session_store)
        else:
            self.session_store = session_store

    # ---------------------------
    # Session Handling
    # ---------------------------
    def get_session(self) -> Optional[SessionData]:
        session_id = current_session_id.get()
        if not session_id:
            return None
        data = self.session_store.get_session(session_id)
        return SessionData(data) if data is not None else None

    def set_session(self, data: Dict[str, Any]) -> bool:
        session_id = current_session_id.get()
        if not session_id:
            return False
        return self.session_store.update_session(session_id, data)

    def update_session(self, updater_func: Callable[[SessionData], None]) -> bool:
        session = self.get_session()
        if not session:
            return False
        updater_func(session)
        return self.set_session(session.raw())

    # ---------------------------
    # Tool Registration
    # ---------------------------
    def tool(self, name: Optional[str] = None, title: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a function as an MCP tool."""

        def decorator(func: Callable):
            tool_name = name or func.__name__
            doc = inspect.getdoc(func) or ""
            tool_description = description or doc.split("\n\n")[0]
            hints = get_type_hints(func)
            hints.pop("return", Any)

            properties = {}
            required = []

            def get_type_schema(type_hint: Any) -> Dict[str, Any]:
                if type_hint is int:
                    return {"type": "integer"}
                elif type_hint is float:
                    return {"type": "number"}
                elif type_hint is bool:
                    return {"type": "boolean"}
                elif type_hint is str:
                    return {"type": "string"}
                if isinstance(type_hint, type) and issubclass(type_hint, Enum):
                    return {"type": "string", "enum": [e.value for e in type_hint]}
                origin = get_origin(type_hint)
                if origin is None:
                    return {"type": "string"}
                if origin in (dict, Dict):
                    args = get_args(type_hint)
                    value_schema = get_type_schema(args[1]) if len(args) > 1 else {"type": "string"}
                    return {"type": "object", "additionalProperties": value_schema}
                if origin in (list, List):
                    args = get_args(type_hint)
                    item_schema = get_type_schema(args[0]) if args else {"type": "string"}
                    return {"type": "array", "items": item_schema}
                return {"type": "string"}

            for param_name, param_type in hints.items():
                properties[param_name] = get_type_schema(param_type)
                required.append(param_name)

            self.tools[tool_name] = {
                "name": tool_name,
                "description": tool_description,
                "inputSchema": {"type": "object", "properties": properties, "required": required},
            }
            self.tool_implementations[tool_name] = func
            return func

        return decorator

    # ---------------------------
    # Prompt Registration
    # ---------------------------
    def prompt(self, name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a function as an MCP prompt."""

        def decorator(func: Callable):
            prompt_name = name or func.__name__
            doc = inspect.getdoc(func) or ""
            prompt_description = description or doc.split("\n\n")[0]
            hints = get_type_hints(func)
            hints.pop("return", None)
            properties = {}
            required = []

            for param_name, param_type in hints.items():
                if param_type is str:
                    schema = {"type": "string"}
                elif param_type is int:
                    schema = {"type": "integer"}
                elif param_type is float:
                    schema = {"type": "number"}
                elif param_type is bool:
                    schema = {"type": "boolean"}
                else:
                    schema = {"type": "string"}
                properties[param_name] = schema
                required.append(param_name)

            self.prompts[prompt_name] = {
                "name": prompt_name,
                "description": prompt_description,
                "inputSchema": {"type": "object", "properties": properties, "required": required},
            }
            self.prompt_implementations[prompt_name] = func
            return func

        return decorator

    # ---------------------------
    # Resource Registration
    # ---------------------------
    def add_resource(self, resource: Resource) -> None:
        self.resources[resource.uri] = resource

    def resource(self, uri: str, name: str, description: Optional[str] = None, mime_type: Optional[str] = None):
        def decorator(func: Callable):
            resource = StaticResource(
                uri=uri, name=name, content="", description=description, mime_type=mime_type or "text/plain"
            )
            resource._content_func = func
            self.resources[uri] = resource
            return func

        return decorator

    # ---------------------------
    # Internal Helpers
    # ---------------------------
    def _create_error_response(
        self,
        code: int,
        message: str,
        request_id: Optional[str] = None,
        error_content: Optional[List[Dict]] = None,
        session_id: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> Dict:
        error = JSONRPCError(code=code, message=message)
        response = JSONRPCResponse(jsonrpc="2.0", id=request_id, error=error, errorContent=error_content)
        headers = {"Content-Type": "application/json", "MCP-Version": "0.6"}
        if session_id:
            headers["MCP-Session-Id"] = session_id
        return {
            "statusCode": status_code or self._error_code_to_http_status(code),
            "body": response.model_dump_json(),
            "headers": headers,
        }

    def _error_code_to_http_status(self, error_code: int) -> int:
        return {
            -32700: 400,
            -32600: 400,
            -32601: 404,
            -32602: 400,
            -32603: 500,
        }.get(error_code, 500)

    def _convert_result_to_content(self, result: Any) -> List[Dict]:

        if isinstance(result, list):
            return [
                content_item  # each individual content object
                for result_item in result  # each raw result from the tool/prompt
                for content_item in self._convert_result_to_content(result_item)
            ]

        if isinstance(result, ToolResult):
            return [result.content[0].model_dump()]

        if isinstance(result, PromptMessage):
            return [result.model_dump()]

        if isinstance(result, bytes):
            import base64
            mime_type = "application/octet-stream"
            if result.startswith(b"\xff\xd8\xff"):
                mime_type = "image/jpeg"
            elif result.startswith(b"\x89PNG\r\n\x1a\n"):
                mime_type = "image/png"
            elif result.startswith(b"GIF87a") or result.startswith(b"GIF89a"):
                mime_type = "image/gif"
            elif result.startswith(b"RIFF") and result[8:12] == b"WEBP":
                mime_type = "image/webp"
            base64_data = base64.b64encode(result).decode("utf-8")
            return [ImageContent(data=base64_data, mimeType=mime_type).model_dump()]
        return [TextContent(text=str(result)).model_dump()]

    def _create_success_response(self, result: Any, request_id: str | None, session_id: Optional[str] = None) -> Dict:
        response = JSONRPCResponse(jsonrpc="2.0", id=request_id, result=result)
        headers = {"Content-Type": "application/json", "MCP-Version": "0.6"}
        if session_id:
            headers["MCP-Session-Id"] = session_id
        return {"statusCode": 200, "body": response.model_dump_json(), "headers": headers}

    # ---------------------------
    # Request Handling
    # ---------------------------
    def handle_request(self, event: Dict, context: Any) -> Dict:
        request_id = None
        session_id = None
        try:
            headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
            session_id = headers.get("mcp-session-id")
            current_session_id.set(session_id or None)

            if event.get("httpMethod") == "DELETE" and session_id:
                if self.session_store.delete_session(session_id):
                    return {"statusCode": 204}
                else:
                    return {"statusCode": 404}

            if headers.get("content-type") != "application/json":
                return self._create_error_response(-32700, "Unsupported Media Type")

            try:
                body = json.loads(event["body"])
                request_id = body.get("id") if isinstance(body, dict) else None
            except json.JSONDecodeError:
                return self._create_error_response(-32700, "Parse error")

            if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or "method" not in body:
                return self._create_error_response(-32700, "Parse error", request_id)

            request = JSONRPCRequest.model_validate(body)

            # ------------------ initialize ------------------
            if request.method == "initialize":
                session_id = self.session_store.create_session()
                current_session_id.set(session_id)
                result = InitializeResult(
                    protocolVersion="2024-11-05",
                    serverInfo=ServerInfo(name=self.name, version=self.version),
                    capabilities=Capabilities(
                        tools={"list": True, "call": True},
                        resources={"list": True, "read": True},
                        prompts={"list": True, "get": True},
                    ),
                )
                return self._create_success_response(result.model_dump(), request.id, session_id)

            if session_id:
                session_data = self.session_store.get_session(session_id)
                if session_data is None:
                    return self._create_error_response(-32000, "Invalid or expired session", request.id, status_code=404)
            elif not isinstance(self.session_store, NoOpSessionStore):
                return self._create_error_response(-32000, "Session required", request.id, status_code=400)

            # ------------------ tools/list ------------------
            if request.method == "tools/list":
                return self._create_success_response({"tools": list(self.tools.values())}, request.id, session_id)

            # ------------------ tools/call ------------------
            if request.method == "tools/call" and request.params:
                tool_name = request.params.get("name")
                tool_args = request.params.get("arguments", {})
                if tool_name not in self.tools:
                    return self._create_error_response(-32601, f"Tool '{tool_name}' not found", request.id, session_id=session_id)
                try:
                    tool_func = self.tool_implementations[tool_name]
                    hints = get_type_hints(tool_func)
                    converted_args = {}
                    for arg_name, arg_value in tool_args.items():
                        arg_type = hints.get(arg_name)
                        if isinstance(arg_type, type) and issubclass(arg_type, Enum):
                            converted_args[arg_name] = arg_type(arg_value)
                        else:
                            converted_args[arg_name] = arg_value
                    result = tool_func(**converted_args)
                    content = self._convert_result_to_content(result)
                    return self._create_success_response({"content": content}, request.id, session_id)
                except Exception as e:
                    logger.exception(f"Error executing tool {tool_name}")
                    return self._create_error_response(-32603, f"Error executing tool: {str(e)}", request.id, [ErrorContent(text=str(e)).model_dump()], session_id)

            # ------------------ prompts/list ------------------
            if request.method == "prompts/list":
                return self._create_success_response({"prompts": list(self.prompts.values())}, request.id, session_id)

            # ------------------ prompts/get ------------------
            if request.method == "prompts/get" and request.params:
                prompt_name = request.params.get("name")
                prompt_args = request.params.get("arguments", {})
                if prompt_name not in self.prompts:
                    return self._create_error_response(-32601, f"Prompt '{prompt_name}' not found", request.id, session_id=session_id)
                try:
                    prompt_func = self.prompt_implementations[prompt_name]
                    result = prompt_func(**prompt_args)
                    content = self._convert_result_to_content(result)
                    return self._create_success_response({"messages": content}, request.id, session_id)
                except Exception as e:
                    logger.exception(f"Error executing prompt {prompt_name}")
                    return self._create_error_response(-32603, f"Error executing prompt: {str(e)}", request.id, [ErrorContent(text=str(e)).model_dump()], session_id)

            # ------------------ resources/list ------------------
            if request.method == "resources/list":
                return self._create_success_response({"resources": [r.model_dump() for r in self.resources.values()]}, request.id, session_id)

            # ------------------ resources/read ------------------
            if request.method == "resources/read":
                if not request.params or not request.params.get("uri"):
                    return self._create_error_response(-32602, "Missing required parameter: uri", request.id, session_id=session_id)
                resource_uri = request.params["uri"]
                if resource_uri not in self.resources:
                    return self._create_error_response(-32601, f"Resource not found: {resource_uri}", request.id, session_id=session_id)
                resource = self.resources[resource_uri]
                try:
                    if hasattr(resource, "_content_func") and resource._content_func is not None:
                        content = resource._content_func()
                        resource_content = ResourceContent(uri=resource_uri, mimeType=resource.mimeType, text=str(content))
                    else:
                        resource_content = resource.read_content()
                    return self._create_success_response({"contents": [resource_content.model_dump()]}, request.id, session_id)
                except Exception as e:
                    logger.exception(f"Error reading resource {resource_uri}")
                    return self._create_error_response(-32603, f"Error reading resource: {str(e)}", request.id, [ErrorContent(text=str(e)).model_dump()], session_id)

            # ------------------ ping ------------------
            if request.method == "ping":
                return self._create_success_response({}, request.id, session_id)

            # ------------------ unknown ------------------
            return self._create_error_response(-32601, f"Method not found: {request.method}", request.id, session_id=session_id)

        except Exception as e:
            logger.exception("Error processing request")
            return self._create_error_response(-32000, str(e), request_id, session_id=session_id)
        finally:
            current_session_id.set(None)
