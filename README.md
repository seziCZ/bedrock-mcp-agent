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

# Useful Commands

```bash
aws s3vectors list-vectors --vector-bucket-name <bucket> --index-name memories --return-metadata
aws s3vectors delete-vectors --vector-bucket-name <bucket> --index-name my-index --keys <key>
aws apigateway get-api-keys --include-values
```

# References

- [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html) – Serverless compute service  
- [AWS Bedrock](https://aws.amazon.com/bedrock/) – Foundation models for language understanding  
- [AWS S3 Vectors](https://aws.amazon.com/s3/features/vectors/) – Object storage for vector embeddings  
- [AWS CDK](https://aws.amazon.com/cdk/) – Infrastructure as code  
- [API Gateway](https://aws.amazon.com/api-gateway/) – Secure API endpoints 
- [Serverless MCP](https://github.com/awslabs/mcp/tree/main/src/mcp-lambda-handler) - Inspiration for Lambda MCP server implementation
- [Serverless MCP Options](https://github.com/awslabs/run-model-context-protocol-servers-with-aws-lambda) - Options regarding MCP serverless deployments
