import datetime
import json
import logging
import os
import textwrap
import uuid
from dataclasses import dataclass, asdict
from typing import Annotated

import boto3
from fastmcp.tools.tool import ToolResult
from mcp.types import PromptMessage, TextContent

# -------------------------
# Configuration
# -------------------------s
SERVERLESS = os.environ.get("serverless_deployment", True)
EMBEDDING_MODEL = os.environ.get("embedding_model", "amazon.titan-embed-text-v2:0")
VECTOR_BUCKET_NAME = os.environ.get("vector_bucket_name", "test-s3-vector-bucket")
VECTOR_INDEX_NAME = os.environ.get("vector_index_name", "memories")

# -------------------------
# Initialize MCP server
# -------------------------
mcp = None
if SERVERLESS:
    from mcp_server.mcp_handler import MCPLambdaHandler
    mcp = MCPLambdaHandler("Lambda MCP Server")

else:
    from fastmcp import FastMCP
    mcp = FastMCP("FastMCP Server")

# -------------------------
# Define MCP model entities
# -------------------------

@dataclass
class Memory:
    """
    Representation of a literal model's memory.
    :param content: The content of the memory.
    :param created: The timestamp when the memory was evoked.
    :param distance: Cosine distance of this memory to a reference vector,
        ranging from 0 (identical) to 1 (completely dissimilar). Defaults to 0.
    """
    content: str
    created: datetime
    distance: float = 0

# -------------------------
# Initialize AWS clients
# -------------------------
bedrock = boto3.client("bedrock-runtime")
s3_vectors = boto3.client("s3vectors")


# -------------------------
# Define MCP tools
# -------------------------

@mcp.tool(
    name="memory.store",
    title="Memory creation Tool",
    description="Stores a memory to enhance future conversations by providing relevant contextual information."
)
def memory_store(
    content: Annotated[str, "The content of the memory."],
) -> ToolResult:
    """
    Stores a memory to enhance future conversations by providing relevant contextual information.
    :param content: The content of the memory to be remembered and recalled later to provide context
    :return: A representation of the stored memory, suitable for both machine and human readability.
    """

    # compose memory to be persisted
    memory = Memory(
        content=content,
        created=datetime.datetime.now()
    )

    # write embeddings into vector index with metadata
    embeddings = _get_embeddings(content)
    s3_vectors.put_vectors(
        vectorBucketName=VECTOR_BUCKET_NAME,
        indexName=VECTOR_INDEX_NAME,
        vectors=[
            {
                "key": uuid.uuid4().hex,
                "data": {"float32": embeddings},
                "metadata": {
                    "content": memory.content,
                    "created": memory.created.isoformat(),
                }
            }
        ]
    )

    # yield the memory
    return ToolResult(
        structured_content=asdict(memory),
        content=memory.content,
    )

@mcp.tool(
    name="memory.recall",
    title="Memory recollection tool",
    description="Recalls memory to be used as relevant contextual information, based on provided context."
)
def memory_recall(
    context: Annotated[str, "Contextual information that relates to the memory to be recalled"],
) -> ToolResult:
    """
    Recalls memory to be used as relevant contextual information, based on provided context
    :param context: Context-full hint that helps recalling the memory
    :return: The most relevant memory, both in machine and human-readable formats
    """

    # query vector index for memories
    embeddings = _get_embeddings(context)
    response = s3_vectors.query_vectors(
        vectorBucketName=VECTOR_BUCKET_NAME,
        indexName="memories",
        queryVector={"float32": embeddings},
        returnMetadata=True,
        returnDistance=True,
        topK=5
    )

    # cease processing if empty
    if not response["vectors"]:
        return ToolResult(
            structured_content=None,
            content=f"I have shared nothing about {context}",
        )

    # reconstruct relevant memories
    memories = [
        Memory(
            content=memory["metadata"]["content"],
            distance=memory["distance"],
            created=datetime.datetime.fromisoformat(
                memory["metadata"]["created"]
            )
        )
        for memory
        in response["vectors"]
    ]

    # sort by relevance, serve in both machine and human-readable formats
    memories = sorted(memories, key=lambda memory: memory.distance)
    return ToolResult(
        structured_content={"memories": [asdict(memory) for memory in memories]},
        content="\n".join(f"- {memory.content}" for memory in memories)
    )

# -------------------------
# Define MCP prompts
# -------------------------
@mcp.prompt(
    name="memory.decide",
    description="Generates prompts to help the LLM decide whether to store a new memory or recall an existing one based on context."
)
def memory_decide() -> list[PromptMessage]:
    """
    Generates prompts to guide the LLM in deciding how to handle memory.s
    :return: A list of PromptMessage objects to assist the LLM's memory decision.
    """
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=textwrap.dedent("""                     
                    You are the MCP server responsible for managing the LLM's memory. The user has consented to allow 
                    you to store, recall, and use all personal information they provide. Only notable, user-specific,
                    non-generic information should be stored. General knowledge, widely-known facts, or trivial 
                    information must not be stored, nor should they trigger recall.

                    Your task is to analyze each incoming user message and determine whether any part of it:
                    
                    1. Should be **stored** in long-term memory for future conversations, or  
                    2. Requires **recalling** existing memory to answer the request accurately.
                    
                    **Rules for Memory Management**
                    
                    1. Only store **user-specific, notable, or non-generic information** that enriches context for future conversations.  
                    2. Do **not** store general knowledge, trivia, or information that is widely known.  
                    3. Store information as **impersonal facts in passive voice**, without first-person references.  
                    4. Rephrase information for clarity and efficient retrieval.  
                    5. If notable information is identified, generate a `memory.store` tool call in plain text.  
                    6. Generate a `memory.recall` tool call **only if the message might involve user-specific, personal, or non-generic information**. Do not recall for general knowledge or trivial queries. Provide broad, generic context to capture all relevant information, even if the value is unknown.  
                    7. Both `content` and `context` must be **plain text strings**, capturing the key concepts of the information.  
                    8.  **Always return a strictly parseable JSON array**, even if there is only one tool call. Do not include quotes, backticks, markdown, explanations, or any text outside the array.  
                    9. If the message contains only general knowledge, trivia, or non-user-specific information, return exactly an empty array: []. Never add any text before or after the array. Only output a JSON array. Do not include any explanations, commentary, notes, or text outside the array. 
                    
                    **JSON Object Structure**
                    
                    For each memory need, output one object:
                    
                    {
                        "tool": "<tool name>",
                        "arguments": {
                            "content" or "context": "<plain text string>"
                        }
                    }
                    
                    **Available MCP Tools**
                    
                    1. `memory.store`  
                       - Stores information that enriches future conversations.  
                       - Examples:
                         [
                             {
                                 "tool": "memory.store",
                                 "arguments": {
                                     "content": "Exploring wild Nordic nature and backpacking are highly favored activities. Trips involving hiking and camping in remote Nordic landscapes are preferred."
                                 }
                             },
                             {
                                 "tool": "memory.store",
                                 "arguments": {
                                     "content": "Instrumental music performed on the piano is highly beloved. Keith Jarrett is regarded as the favorite composer."
                                 }
                             }                            
                         ]
                    
                    2. `memory.recall`  
                       - Retrieves previously stored contextual memory based on the essential concepts of the user’s message.  
                       - Examples:
                         [
                             {
                                 "tool": "memory.recall",
                                 "arguments": {
                                     "context": "Traveling to Asia is imminent. Dining opportunities during the visit are highly anticipated."
                                 }
                             },
                             {
                                 "tool": "memory.recall",
                                 "arguments": {
                                     "context": "Attendance at the upcoming music festival in Brno is highly anticipated. The event is looked forward to with excitement."
                                 }
                             }                             
                         ]
                """
                )
            )
        )
    ]

# -------------------------
# Define helper methods
# -------------------------

def _get_embeddings(text: str) -> list[str]:
    """
    Yields embeddings for the given text, allowing for semantic similarity evaluation.
    :param text: Text whose embedding is to be yielded.
    :return: Embeddings for the given text.
    """

    # generate embedding using Bedrock
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
    )

    # yield the embedding as string encoded float
    response_body = response["body"].read()
    response_parsed = json.loads(response_body)
    return response_parsed["embedding"]

# -------------------------
# Run AWS Lambda server
# -------------------------
def handler(event, context):
    """
    Lambda handler that processes API Gateway requests via MCP.
    :param event: API Gateway event containing HTTP request info and JSON-RPC body.
    :param context: AWS Lambda runtime information (memory, request ID, etc.)
    :return: Standard API Gateway Proxy response containing JSON-RPC result.
    """
    logging.info("Server triggered for %s", event)
    return mcp.handle_request(event, context)

# -------------------------
# Run FastMCP server
# -------------------------
if __name__ == "__main__" and not SERVERLESS:
    """
    Entry point for running the FastMCP server. Starts `mcp.run()` to handle stdio or MCP clients. 
    Only used for FastMCP server deployments; serverless implementations do not spawn a long-running process.
    """
    mcp.run()
