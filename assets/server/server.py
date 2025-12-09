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

# -------------------------
# Configuration
# -------------------------

DEPLOYMENT_MODE = os.environ.get("DEPLOYMENT_MODE", "lambda")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")

VECTOR_BUCKET_NAME = os.environ.get("VECTOR_BUCKET_NAME", "test-s3-vector-bucket")
VECTOR_INDEX_NAME = os.environ.get("VECTOR_INDEX_NAME", "memories")

# -------------------------
# Initialize MCP server
# -------------------------

mcp = None
if DEPLOYMENT_MODE == "lambda":
    from mcp_server.mcp_handler import MCPLambdaHandler
    mcp = MCPLambdaHandler("AWS Lambda MCP Server")

else:
    from fastmcp import FastMCP
    mcp = FastMCP(
        name="FastMCP Server",
        host="0.0.0.0",
        port=8000,
        stateless_http=True,
        streamable_http_path="/mcp"
    )

# -------------------------
# Define MCP model entities
# -------------------------

@dataclass
class Note:
    """
    Represents a single entry in the user's notebook.
    :param content: The textual content of the note.
    :param created: Timestamp indicating when the note was created.
    :param distance: Cosine distance from a reference vector, where
        0 indicates identical similarity and 1 indicates complete dissimilarity.
        Defaults to 0.
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
    name="note_take",
    title="Note Capture Tool",
    description=textwrap.dedent("""
        Takes a user-instructed note and saves it as long-term memory.

        Use this tool only when the user explicitly asks to take a note, remember something,
        or store information for future context. Extract the meaningful content, clean it
        lightly for clarity, and provide a plain-text string that preserves all essential
        details.

        The tool returns:
          • structured_content: a JSON object containing the stored note content and timestamp
          • content: a concise, human-readable summary of what was saved
    """)
)
def note_take(
    content: Annotated[str, "The content of the note."],
) -> ToolResult:
    """
    This tool should be invoked when the user explicitly asks to take a note, jot something down,
    or save information for later. The input should be a clean, plain-text representation of
    the note while preserving all essential details.
    :param content: The text of the note to be stored.
    :return: The created note, both in machine and human-readable formats
    """

    # compose note to be persisted
    note = Note(
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
                    "content": note.content,
                    "created": note.created.isoformat(),
                }
            }
        ]
    )

    # yield the note
    return ToolResult(
        structured_content=asdict(note),
        content=note.content,
    )

@mcp.tool(
    name="note_find",
    title="Note Find Tool",
    description=textwrap.dedent("""
        Finds and returns previously saved notes that are relevant to the user's query.

        Use this tool whenever the user asks to recall, find, look up, or search for
        information that may have been stored earlier. The user will provide a
        context-rich hint (keywords, topics, or phrases), and the tool will perform a
        semantic search to locate the most relevant notes.

        The tool returns:
          • structured_content: a JSON object containing the matching notes with their
            content, timestamp, and relevance information
          • content: a readable summary listing the retrieved notes
    """)
)
def note_find(
    context: Annotated[str, "Contextual information that relates to the note to be found"],
) -> ToolResult:
    """
    Use this tool when the user asks to recall, find, or look up notes based on keywords, topics,
    or other contextual hints. The tool performs a semantic search over all saved notes and returns
    the most relevant matches.
    :param context: A context-rich query or hint used to locate relevant notes.
    :return: The most relevant notes, both in machine and human-readable formats
    """

    # query vector index for notes
    embeddings = _get_embeddings(context)
    response = s3_vectors.query_vectors(
        vectorBucketName=VECTOR_BUCKET_NAME,
        indexName=VECTOR_INDEX_NAME,
        queryVector={"float32": embeddings},
        returnMetadata=True,
        returnDistance=True,
        topK=5
    )

    # cease processing if empty
    if not response["vectors"]:
        return ToolResult(
            structured_content=None,
            content=f"No '{context}' relevant notes available.",
        )

    # reconstruct relevant notes
    notes = [
        Note(
            content=note["metadata"]["content"],
            distance=note["distance"],
            created=datetime.datetime.fromisoformat(
                note["metadata"]["created"]
            )
        )
        for note
        in response["vectors"]
    ]

    # sort by relevance, serve in both machine and human-readable formats
    notes = sorted(notes, key=lambda note: note.distance)
    return ToolResult(
        structured_content={"notes": [asdict(note) for note in notes]},
        content="\n".join(f"- {note.content}" for note in notes)
    )

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
if __name__ == "__main__" and isinstance(mcp, FastMCP):
    """
    Entry point for running the FastMCP server. Starts `mcp.run()` to handle stdio or MCP clients. 
    Only used for FastMCP server deployments; serverless implementations do not spawn a long-running process.
    """
    mcp.run()
