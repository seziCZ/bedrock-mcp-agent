import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import boto3
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

from builder import PromptBuilder

# -------------------------
# Configuration
# -------------------------

API_KEY_HEADER = os.environ.get("api_key_header", "X-API-Key")
MCP_ENDPOINT = os.environ.get("mcp_endpoint", "https://localhost:8080")
LLM_MODEL = os.environ.get("llm_model", "us.amazon.nova-lite-v1:0")

# -------------------------
# Define MCP model entities
# -------------------------

@dataclass
class MemoryRequest:
    """
    Represents a request to perform a specific tool action with given arguments.
    :param tool: The name or identifier of the tool to execute.
    :param arguments: A dictionary of arguments or parameters to pass to the tool.
    """
    tool: str
    arguments: dict

# -------------------------
# Initialize MCP and AWS clients
# -------------------------

bedrock = boto3.client("bedrock-runtime")
mcp_factory = lambda x_api_key: Client(
    init_timeout=timedelta(seconds=30),
    timeout=timedelta(seconds=30),
    transport=StreamableHttpTransport(
        headers={API_KEY_HEADER: x_api_key},
        url=MCP_ENDPOINT,
    )
)

# -----------------------
# Lambda handler
# -----------------------

def handler(event, context) -> dict[str, Any]:
    """
    Demo implementation of a Bedrock agent capable of taking notes on behalf of the caller.
    @param event: The event data that triggered the Lambda function. This is a dictionary containing request parameters, payload, or other triggering information.
    @param context: Runtime information provided by AWS Lambda. Contains methods and properties like function name, memory limit, request ID, and remaining execution time.
    @return: The response from the Lambda function. Typically a dictionary, string, or other serializable object that represents the function's result.
    """
    logging.info("Agent triggered for %s", event)
    return asyncio.run(handle(event, context))

async def handle(event, context) -> dict[str, Any]:
    """
    synchronous event handler enabling the use of asyncio-based FastMCP library constructs.
    @param event: The event data that triggered the Lambda function. This is a dictionary containing request parameters, payload, or other triggering information.
    @param context: Runtime information provided by AWS Lambda. Contains methods and properties like function name, memory limit, request ID, and remaining execution time.
    @return: The response from the Lambda function. Typically a dictionary, string, or other serializable object that represents the function's result.
    """
    api_event = APIGatewayProxyEventV2(event)
    api_key = api_event.headers.get(API_KEY_HEADER)
    async with mcp_factory(api_key) as mcp_client:

        # create prompts for LLM to decide on MCP server usage
        server_prompts = await mcp_client.get_prompt("memory.decide")
        prompt_builder = PromptBuilder(prompts=server_prompts.messages)
        prompt_builder.add_user_prompt(api_event.body)

        # submit prompts to LLM, let it decide on MCP server usage
        tool_usage_requests = _parse_llm_request(
            llm_request=bedrock.invoke_model(
                modelId=LLM_MODEL,
                body=prompt_builder.build()
            )
        )

        # extend conversation context with MCP mediated memory
        prompt_builder = PromptBuilder()
        for request in tool_usage_requests:
            tool_response = await mcp_client.call_tool(request.tool, request.arguments)
            prompt_builder.add_user_prompt(tool_response.content[0].text)
            logging.info("Added '%s' context: %s", request.tool, tool_response.content[0].text)

        # submit prompts to LLM, let it respond to the user
        prompt_builder.add_user_prompt(api_event.body)
        return {
            "statusCode": 200,
            "body": _parse_llm_response(
                llm_response=bedrock.invoke_model(
                    modelId=LLM_MODEL,
                    body=prompt_builder.build()
                )
            )
        }

def _parse_llm_response(llm_response: dict) -> str:
    """
    Extracts the textual content of the LLM’s response from its raw dictionary structure.
    :param llm_response: The raw response dictionary returned by the LLM, which includes a 'body' key containing a JSON payload.
    :return: The string text content extracted from the LLM response.
    """
    mcp_request_body = json.loads(llm_response["body"].read())
    return mcp_request_body['output']['message']['content'][0]['text']

def _parse_llm_request(llm_request: dict) -> list[MemoryRequest]:
    """
    Converts an LLM response into a NoteRequest object for MCP execution.
    :param llm_request: The raw request dictionary returned by the LLM.
    :return: A NoteRequest object with 'tool' and 'arguments' fields, or None if no tool is selected.
    """
    str_response = _parse_llm_response(llm_request)
    mcp_request_json = json.loads(str_response)
    return [MemoryRequest(**info) for info in mcp_request_json]
