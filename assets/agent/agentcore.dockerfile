# use slim 3.12 base image
FROM python:3.12-slim

# satisfy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy agent relevant assets
COPY __init__.py .
COPY agentcore.py .
COPY agent.py .

# set the entry point
EXPOSE 8000
CMD ["python", "agentcore.py"]
