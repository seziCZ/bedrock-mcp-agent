# use slim 3.12 base image
FROM python:3.12-slim

# disable serveless mode
ENV DEPLOYMENT_MODE=FastMCP

# satisfy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy server relevant assets
COPY __init__.py .
COPY server.py .

# Set the entry point
EXPOSE 8000
CMD ["python", "server.py"]
