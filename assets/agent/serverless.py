import asyncio
import os
from typing import Any, Dict

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2, event_source
from aws_lambda_powertools.utilities.typing import LambdaContext

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
# Lambda handler
# -----------------------

@event_source(data_class=APIGatewayProxyEventV2)
def handler(
    event: APIGatewayProxyEventV2,
    context: LambdaContext
) -> Dict[str, Any]:
    """
    API Gateway → Lambda entrypoint for invoking an MCP-enabled LangChain agent.
    @param event: The AWS Lambda event payload, an API Gateway request
    @param context: AWS Lambda runtime context providing metadata
    @return: The response produced by the asynchronous handler, formatted as a dictionary
    """

    # invoke agent asynchronously
    response = asyncio.run(
        main=agent.invoke(
            prompt=event.body
        )
    )

    # format Lambda response
    return {
        "statusCode": 200,
        "body": response,
    }
