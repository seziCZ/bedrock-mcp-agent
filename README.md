# Serverless Bedrock Agent with MCP Context

This project demonstrates a fully serverless architecture for a Bedrock-based LLM agent, where MCP servers handle the agent’s memory and context management. The architecture allows the agent to dynamically decide whether to store new information or recall relevant past memories to generate context-aware responses. It leverages AWS Bedrock models for language understanding and embeddings, S3 Vector tables for storing and querying semantic memory, and containerized AWS Lambda functions to host both the agent and MCP servers. The entire infrastructure is orchestrated using Python CDK.

---

## Key Concept

- **Serverless Agent**: Lambda-based agent queries Bedrock LLMs for responses.  
- **Lambda-Hosted MCP**: MCP server runs entirely on AWS Lambda, managing long-term memory and embeddings. No dedicated servers required.  
- **S3 Vector Store**: Persists embeddings for semantic memory and context-aware responses.  
- **Authentication**: Both Agent and Server API Gateway endpoints are secured via **API key** in the `X-API-Key` header.  

---

## Architecture
    
      ┌────────────┐
      │  User/API  │
      └─────┬──────┘
            │
            ▼
    ┌───────────────┐
    │  Agent Lambda │
    │  (Bedrock)    │
    └─────┬─────────┘
          │ invokes tools
          ▼
    ┌───────────────┐
    │ Server Lambda │
    │  (Memory MCP) │
    └─────┬─────────┘
          │ stores/queries
          ▼
     ┌───────────┐
     │ S3 Vectors│
     └───────────┘


**Flow:**

- **Agent Lambda**: Receives API requests, constructs prompts, and interacts with the MCP server to decide on memory usage.
- **Server Lambda**: Handles `memory.store` and `memory.recall` tools, backed by an S3 Vector store for embeddings.

---

