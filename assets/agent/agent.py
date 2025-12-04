import asyncio
import logging
import os
from typing import Any

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# -------------------------
# Configuration
# -------------------------

API_KEY_HEADER = os.environ.get("api_key_header", "X-API-Key")
MCP_ENDPOINT = os.environ.get("mcp_endpoint", "https://localhost:8080")
LLM_MODEL = os.environ.get("llm_model", "us.amazon.nova-lite-v1:0")

# -------------------------
# Initialize AWS Bedrock client
# -------------------------

llm = ChatBedrockConverse(
    model=LLM_MODEL,
    temperature=0.2,
    top_p=0.9,
    max_tokens=512
)

# -----------------------
# Lambda handler
# -----------------------

def handler(event, context) -> dict[str, Any]:
    """
    Synchronous AWS Lambda entrypoint for the Bedrock-powered note-taking agent. Wraps the asynchronous
    `handle` function so the Lambda runtime can invoke it without native asyncio support.
    @param event: The AWS Lambda event payload, an API Gateway request
    @param context: AWS Lambda runtime context providing metadata
    @return: The response produced by the asynchronous handler, formatted as a dictionary
    """
    logging.info("Agent triggered for %s", event)
    return asyncio.run(handle(event, context))

async def handle(event, context) -> dict[str, Any]:
    """
     Asynchronous handler that orchestrates the full agent workflow:
      1. Parses the incoming API Gateway event.
      2. Creates an MCP client authenticated with the caller's API key.
      3. Retrieves the MCP-exposed tools and injects them into a Bedrock-backed agent.
      4. Invokes the agent with the user's question and returns the final model reply.
    @param event: The AWS Lambda event payload, an API Gateway request
    @param context: AWS Lambda runtime context providing metadata
    @return: The response produced by the asynchronous handler, formatted as a dictionary
    """

    # extract caller's API key from headers
    api_event = APIGatewayProxyEventV2(event)
    api_key = api_event.headers.get(API_KEY_HEADER)

    # discover MCP tools exposed by the configured MCP server
    mcp_client = _get_mcp_client(api_key)
    mcp_tools = await mcp_client.get_tools()

    # create a LangChain agent backed by Bedrock and MCP tools
    graph = create_agent(
        model=llm,
        tools=mcp_tools,
        debug=True
    )

    # build the message list for the agent.
    prompts = {
        "messages": [
            HumanMessage(
                content=api_event.body
            )
        ]
    }

    # run the agent and return the last message as the HTTP response body.
    responses = await graph.ainvoke(prompts)
    return {
        "statusCode": 200,
        "body": responses["messages"][-1].content
    }

def _get_mcp_client(x_api_key: str) -> MultiServerMCPClient:
    """
    Yields and configures a MultiServerMCPClient, authenticated using the given API key.
    :param x_api_key: The API key to be used when authetnticating against the MCP server
    :return: An initialized MultiServerMCPClient instance.
    """
    return MultiServerMCPClient({
        "mcp_server": {
            "transport": "streamable_http",
            "url": MCP_ENDPOINT,
            "headers": {
                API_KEY_HEADER: x_api_key,
            },
        }
    })
