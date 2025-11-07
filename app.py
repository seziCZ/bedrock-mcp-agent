#!/usr/bin/env python3
"""
CDK App entry point: deploys the demo stack.
This stack is deployed to us-east-1, the only region currently supporting S3 Vector buckets.
"""

import os
import aws_cdk as cdk

from cdk.demo_stack import DemoStack

# create CDK app
app = cdk.App()

# create CF stack
DemoStack(
    scope=app,
    id="DemoStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region="us-east-1"  # only region with S3 vectors
    ),
)

# synthesize CF template
app.synth()
