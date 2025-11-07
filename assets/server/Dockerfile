# Use AWS Lambda Python 3.12 base image
FROM public.ecr.aws/lambda/python:3.12

# Copy server relevant assets
COPY . .

# Satisfy dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a writable MCP home inside /tmp
ENV HOME=/tmp

# Set the CMD to the handler
CMD ["server.handler"]
