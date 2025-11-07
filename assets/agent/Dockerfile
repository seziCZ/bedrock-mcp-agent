# Use AWS Lambda Python 3.11 base image
FROM public.ecr.aws/lambda/python:3.11

# Copy server relevant assets
COPY . .

# Satisfy dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the CMD to the handler
CMD ["agent.handler"]
