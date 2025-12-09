import hashlib
from typing import Dict, Optional

import cdk_s3_vectors as s3_vectors
from aws_cdk import Duration, aws_lambda, aws_apigateway, CfnOutput
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk.aws_apigateway import ApiKey, MethodOptions
from aws_cdk.aws_bedrock_agentcore_alpha import Runtime, AgentRuntimeArtifact, \
    RuntimeAuthorizerConfiguration
from constructs import Construct


class S3VectorBucket(Construct):
    """
    A construct that provisions an S3-based vector storage bucket and
    an associated index for storing embeddings or vectorized data.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        bucket_name: str,
        index_name: str,
    ) -> None:
        """
        Constructor.
        :param scope: The parent construct.
        :param id: The scoped construct ID.
        :param bucket_name: The base name for the S3 bucket.
        :param index_name: The name of the vector index.
        """
        super().__init__(scope, id)
        encoded_id = id.encode()
        suffix_id = hashlib.md5(encoded_id).hexdigest()[:8]

        # Create S3 vector bucket for memory storage
        self.bucket = s3_vectors.Bucket(
            scope=self,
            id=f"{id}Bucket",
            vector_bucket_name=f"{bucket_name}-{suffix_id}",
        )

        # Create index for storing vector embeddings
        self.index = s3_vectors.Index(
            scope=self,
            id=f"{id}Index",
            vector_bucket_name=self.bucket.vector_bucket_name,
            index_name=index_name,
            data_type="float32",
            dimension=1024,
            distance_metric="cosine",
        )

        # Establish dependencies
        self.index.node.add_dependency(self.bucket)


class RestApi(Construct):
    """
    A construct that defines a REST API backed by a Lambda function,
    providing an API Gateway endpoint for the deployed container.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        api_key: ApiKey,
        directory: str,
        file: str = "serverless.dockerfile",
        env: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Constructor.
        :param scope: The parent construct.
        :param id: The scoped construct ID.
        :param api_key: An ApiKey construct that provides the API key used for authentication.
        :param directory: The directory containing the Docker image asset.
        :param file: Name of the Dockerfile within ``directory`` to use when building the container image.
        :param env: Optional environment variables for the Lambda function.
        """
        super().__init__(scope, id)

        # create the Lambda function from a Docker image
        self.function = aws_lambda.DockerImageFunction(
            scope=self,
            id=f"{id}Lambda",
            retry_attempts=0,
            code=aws_lambda.DockerImageCode.from_image_asset(
                directory=directory,
                file=file,
            ),
            memory_size=512,
            timeout=Duration.seconds(30),
            environment=env or {},
        )

        # create API Gateway endpoint that routes requests to the Lambda
        self.api = aws_apigateway.LambdaRestApi(
            scope=self,
            id=f"{id}Api",
            handler=self.function,
            rest_api_name=f"{id} API",
            default_method_options=MethodOptions(
                api_key_required=True,
            )
        )

        # add usage plan for key based authentication
        self.plan = self.api.add_usage_plan(
            id=f"{id}Plan",
            name=f"{id} Plan",
        )

        self.plan.add_api_key(api_key)
        self.plan.add_api_stage(
            stage=self.api.deployment_stage
        )


class AgentRuntime(Construct):
    """
    Deploys a LangChain-based agent as a containerized AgentCore Runtime.
    This construct packages a Dockerized agent implementation (typically a
    LangChain application) and hosts it in Amazon Bedrock AgentCore. It:

      • Builds the Docker image from a local directory into Amazon ECR.
      • Creates an AgentCore Runtime that executes the container.
      • Applies IAM-based authorization for invoking the runtime.
      • Passes optional environment variables into the running agent.

    :param scope: The parent construct.
    :param id: The scoped construct ID.
    :param directory: The directory containing the Docker image asset.
    :param file: Name of the Dockerfile within ``directory`` to use when building the container image.
    :param env: Optional environment variables passed into the MCP container.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        directory: str,
        file: str = "agentcore.dockerfile",
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Constructor.
        :param scope: The parent construct.
        :param id: The scoped construct ID.
        :param directory: Path containing `bedrock.dockerfile` used to build the container image.
        :param env: Optional environment variables for the MCP server container.
        """
        super().__init__(scope, id)

        # build the Docker image into ECR
        ecr_image = ecr_assets.DockerImageAsset(
            scope=self,
            id="Image",
            directory=directory,
            file=file,
            platform=ecr_assets.Platform.LINUX_ARM64
        )

        # compose runtime
        self.runtime = Runtime(
            scope=self,
            id="Runtime",
            runtime_name=f"{id}Runtime",
            environment_variables=env,
            authorizer_configuration=RuntimeAuthorizerConfiguration.using_iam(),
            agent_runtime_artifact=AgentRuntimeArtifact.from_ecr_repository(
                repository=ecr_image.repository,
                tag=ecr_image.image_tag
            ),
        )

        CfnOutput(
            scope=self,
            id="RuntimeArn",
            description="AgentCore Runtime ARN for CLI invocations",
            value=self.runtime.agent_runtime_arn
        )
