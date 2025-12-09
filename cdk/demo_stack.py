from aws_cdk import Stack, aws_iam
from aws_cdk.aws_apigateway import ApiKey
from aws_cdk.aws_secretsmanager import Secret, SecretStringGenerator
from constructs import Construct

from cdk.constructs import S3VectorBucket, RestApi, AgentRuntime


class DemoStack(Stack):
    """
    Stack that provisions the infrastructure required by the agent. It includes an API Gateway endpoint for
    invoking the agent, as well as all necessary resources to support the MCP memory management server.
    """

    LLM_MODEL = "global.amazon.nova-2-lite-v1:0"
    EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

    def __init__(
            self,
            scope: Construct,
            id: str,
            **kwargs
    ) -> None:
        """
        Initializes the stack and defines the AWS resources within it.
        :param scope: The scope in which this construct is defined (usually the app or parent stack).
        :param id: The unique identifier for this construct within the scope.
        :param kwargs: Additional keyword arguments passed to the base Stack class.
        """
        super().__init__(scope, id, **kwargs)

        # create bucket for embeddings
        memory_bucket = S3VectorBucket(
            scope=self,
            id="Memory",
            bucket_name="memory-bucket",
            index_name="memories"
        )

        # ------------------------------------------------------------------
        # Custom Lambda based deployment
        # ------------------------------------------------------------------

        # create API key
        api_secret = Secret(
            scope=self,
            id="ApiSecret",
            generate_secret_string=SecretStringGenerator(
                exclude_punctuation=True,
                password_length=32
            )
        )

        api_key = ApiKey(
            scope=self,
            id="ApiKey",
            value=api_secret.secret_value.unsafe_unwrap()
        )

        # create MCP server API
        server_api = RestApi(
            scope=self,
            id="Server",
            directory="assets/server",
            api_key=api_key,
            env={
                "EMBEDDING_MODEL": self.EMBEDDING_MODEL,
                "VECTOR_BUCKET_NAME": memory_bucket.bucket.vector_bucket_name,
                "VECTOR_INDEX_NAME": memory_bucket.index.index_name
            }
        )

        # create agent API
        agent_api = RestApi(
            scope=self,
            id="Agent",
            directory="assets/agent",
            api_key=api_key,
            env={
                "LLM_MODEL": self.LLM_MODEL,
                "MCP_ENDPOINTS": server_api.api.url,
                "API_KEY": api_secret.secret_value.unsafe_unwrap(),
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


        # ------------------------------------------------------------------
        # AWS Bedrock AgentCore Runtime deployment
        # ------------------------------------------------------------------

        agent_runtime = AgentRuntime(
            scope=self,
            id="AgentCore",
            directory="assets/agent",
            env={
                "LLM_MODEL": self.LLM_MODEL,
                "MCP_ENDPOINTS": server_api.api.url,
                "API_KEY": api_secret.secret_value.unsafe_unwrap(),
            }
        )

        agent_runtime.runtime.add_to_role_policy(policies)
