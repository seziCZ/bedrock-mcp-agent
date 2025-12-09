# use AWS Lambda Python 3.12 base image
FROM public.ecr.aws/lambda/python:3.12

# satisfy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy server relevant assets
COPY __init__.py .
COPY mcp_server ./mcp_server
COPY server.py .

# set the CMD to the handler
CMD ["server.handler"]