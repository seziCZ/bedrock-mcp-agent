# Serverless Bedrock Agent with MCP Context

This project demonstrates a fully serverless architecture for a Bedrock-powered LLM agent, where an MCP server manages note creation, retrieval, and semantic search using AWS S3 Vectors.

The agent uses AWS Bedrock for language reasoning and LangChain for agent orchestration, tool routing, and multi-step decision-making. The same agent container can be executed in two different hosting environments:

1. **API Gateway → Lambda** (direct invocation of the Dockerized agent)
2. **Bedrock AgentCore Runtime** (Bedrock runs the agent container itself)

Both the agent and the MCP server are provisioned using the Python AWS CDK.

---

## Key Concept

- **Serverless Agent (API Gateway Path)**:  
  A Dockerized LangChain agent deployed to AWS Lambda and invoked through API Gateway.  
  This path uses an API key (`X-API-Key`) for authentication.

- **AgentCore Runtime (Direct Bedrock Execution)**:  
  Bedrock AgentCore hosts and runs the *same agent container directly*, without a Lambda wrapper.  
  AgentCore handles planning, tool routing, validation, retries, and multi-step reasoning.  
  Authentication uses **IAM**, not API keys.

- **LangChain Orchestration**:  
  LangChain manages agent reasoning, decides when to call MCP tools, structures tool invocation arguments, and supports multi-step flows across both hosting environments.

- **Lambda-Hosted MCP**:  
  MCP server running fully on AWS Lambda, responsible for storing and retrieving user notes.

- **Persistent Note Store**:  
  Notes are represented as vector embeddings and stored in an S3 Vector Index.

- **Authentication**:  
  - **API Gateway route** → `X-API-Key`  
  - **AgentCore route** → IAM-based authorization

---

## Architecture

                    ┌──────────────┐
                    │    User/API  │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
    ┌──────────────────┐     ┌──────────────────────┐
    │ API Gateway      │     │  AgentCore Runtime   │
    │  (X-API-Key)     │     │   (IAM Auth)         │
    └──────┬───────────┘     └──────────┬───────────┘
           │                            │
           ▼                            ▼
    ┌──────────────────┐         ┌──────────────────┐
    │ Agent Container  │         │ Agent Container  │
    │  (via Lambda)    │         │ (via AgentCore)  │
    └──────┬───────────┘         └──────┬───────────┘
           │ invokes tools              │ invokes tools
           └──────────────┬─────────────┘
                          ▼
                 ┌──────────────────┐
                 │ Server Lambda    │
                 │   (Notes MCP)    │
                 └──────┬───────────┘
                        │ stores/queries
                        ▼
                 ┌───────────────┐
                 │  S3 Vectors   │
                 └───────────────┘


**Flow:**

- **API Gateway Path**  
  User → API Gateway → Lambda → LangChain Agent (Docker) → MCP Server → S3 Vectors

- **AgentCore Path**  
  User → AgentCore (direct container execution) → MCP Server → S3 Vectors

---

# Useful Commands

```bash
aws s3vectors list-vectors --vector-bucket-name <bucket> --index-name memories --return-metadata
aws s3vectors delete-vectors --vector-bucket-name <bucket> --index-name my-index --keys <key>
aws bedrock-agentcore invoke-agent-runtime --agent-runtime-arn <runtime-arn> --payload <base64-json> <output-file>
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
