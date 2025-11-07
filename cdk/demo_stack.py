from aws_cdk import Stack, aws_iam
from aws_cdk.aws_apigateway import ApiKey
from constructs import Construct

from cdk.constructs import S3VectorBucket, RestApi


class DemoStack(Stack):
    """
    Stack that provisions the infrastructure required by the agent. It includes an API Gateway endpoint for
    invoking the agent, as well as all necessary resources to support the MCP memory management server.
    """

    LLM_MODEL = "us.amazon.nova-lite-v1:0"
    EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initializes the stack and defines the AWS resources within it.
        :param scope: The scope in which this construct is defined (usually the app or parent stack).
        :param construct_id: The unique identifier for this construct within the scope.
        :param kwargs: Additional keyword arguments passed to the base Stack class.
        """
        super().__init__(scope, construct_id, **kwargs)

        # create bucket for embeddings
        memory_bucket = S3VectorBucket(
            scope=self,
            id="Memory",
            bucket_name="memory-bucket",
            index_name="memories"
        )

        # create API key
        api_key = ApiKey(
            scope=self,
            id="ApiKey",
        )

        # create MCP server API
        server_api = RestApi(
            scope=self,
            id="Server",
            directory="assets/server",
            api_key=api_key,
            env={
                "llm_model": self.LLM_MODEL,
                "embedding_model": self.EMBEDDING_MODEL,
                "vector_bucket_name": memory_bucket.bucket.vector_bucket_name,
                "vector_index_name": memory_bucket.index.index_name
            }
        )

        # create agent API
        agent_api = RestApi(
            scope=self,
            id="Agent",
            directory="assets/agent",
            api_key=api_key,
            env={
                "llm_model": self.LLM_MODEL,
                "mcp_endpoint": server_api.api.url
            }
        )

        # update policies of API handlers
        policies = aws_iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "s3vectors:GetVectors",
                "s3vectors:PutVectors",
                "s3vectors:QueryVectors",
            ],
            resources=["*"]
        )

        server_api.function.add_to_role_policy(policies)
        agent_api.function.add_to_role_policy(policies)