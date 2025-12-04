# Serverless Bedrock Agent with MCP Context

This project demonstrates a fully serverless architecture for a Bedrock-powered LLM agent, where an MCP server manages note creation, retrieval, and semantic search using AWS S3 Vectors.

The agent uses AWS Bedrock for language reasoning and LangChain for agent orchestration, tool routing, and multi-step decision-making. Both the agent and MCP server run entirely on AWS Lambda, with infrastructure provisioned via the Python AWS CDK.

---

## Key Concept

- **Serverless Agent**: Lambda-hosted agent that interacts with AWS Bedrock LLMs to answer questions and invoke MCP tools.
- **LangChain Orchestration**: LangChain manages agent reasoning, decides when to call MCP tools, structures tool invocation arguments, and constructs multi-step interactions automatically.
- **Lambda-Hosted MCP**: MCP server running fully on AWS Lambda, responsible for storing and retrieving user notes.
- **Persistent Note Store**: Notes are represented as vector embeddings and stored in an S3 Vector Index
- **Authentication**: Both Agent and MCP Server API Gateway endpoints are secured via an API key in the X-API-Key header.  

---

## Architecture
    
      ┌────────────┐
      │  User/API  │
      └─────┬──────┘
            │
            ▼
    ┌──────────────────┐
    │  Agent Lambda    │
    │ (Bedrock +       │
    │   LangChain)     │
    └─────┬────────────┘
          │ invokes tools
          ▼
    ┌──────────────────┐
    │ Server Lambda    │
    │  (Notes MCP)     │
    └─────┬────────────┘
          │ stores/queries
          ▼
     ┌───────────────┐
     │  S3 Vectors   │
     └───────────────┘



**Flow:**

- **Agent Lambda**: Receives API requests, initializes a LangChain-orchestrated Bedrock agent, and invokes MCP tools as needed to create or search notes.
- **Server Lambda**: Implements the MCP note-management tools, embedding and storing notes in an S3 Vectors index and performing vector similarity search for note retrieval.

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
- [LangChain](https://python.langchain.com/) – Agent orchestration, tool routing, and reasoning framework  
- [langchain-aws](https://python.langchain.com/docs/integrations/providers/aws) – Bedrock model bindings and AWS-native LangChain integrations  
- [langchain-mcp-adapters](https://github.com/ModelContextProtocol/langchain-mcp-adapters) – MCP adapter layer enabling LangChain agents to consume MCP tools
- [Serverless MCP](https://github.com/awslabs/mcp/tree/main/src/mcp-lambda-handler) – Inspiration for Lambda-based MCP server implementation  
- [Serverless MCP Options](https://github.com/awslabs/run-model-context-protocol-servers-with-aws-lambda) – Options and patterns for running MCP servers in serverless environments  
