import asyncio
import os
from typing import Dict, Any

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext

from agent import Agent

# -----------------------
# Agent instantiation
# -----------------------

agent = Agent(
    mcp_endpoints=os.environ["MCP_ENDPOINTS"].split(","),
    mcp_headers={"X-API-Key": os.environ["API_KEY"]},
    llm_model=os.environ["LLM_MODEL"],
)

# -----------------------
# Bedrock handler
# -----------------------

app = BedrockAgentCoreApp()

@app.entrypoint
def handler(
        payload: Dict[str, Any],
        context: RequestContext,
) -> Dict[str, Any]:
    """
    AgentCore entrypoint that invokes an MCP-enabled LangChain agent.
    @param payload: A dictionary representing the request payload. It must contain
        a `prompt` field with the natural-language input to be processed by the
        agent. Additional fields may be included but are optional.
    @param context: Request metadata provided by AgentCore, including the session identifier
        (``context.session_id``), HTTP headers, and the underlying request object.
    @return: A dictionary containing the agent's response. On success, the result
        is returned under the `result` key.
    """

    # invoke agent asynchronously
    response = asyncio.run(
        main=agent.invoke(
            prompt=payload["prompt"],
        )
    )

    # format AgentCore response
    return {"result": response}


if __name__ == "__main__":
    """
    When executed directly (e.g., in a container), start the AgentCore app server.
    """
    app.run()
