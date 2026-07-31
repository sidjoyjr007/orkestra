FROM python:3.11-slim

WORKDIR /app

# Install docker CLI for Docker-out-of-Docker sandbox tool execution
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

# Install orkestra from source
COPY pyproject.toml .
COPY README.md .
COPY src ./src
RUN pip install --no-cache-dir .

# Copy and install the runner specific requirements
COPY deployments/runner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the ChromaDB ONNX models so it doesn't happen at runtime
RUN python -c "import chromadb.utils.embedding_functions as ef; ef.DefaultEmbeddingFunction()(['test'])"

# Copy the runner script
COPY deployments/runner/runner.py .

EXPOSE 8000

CMD ["python", "runner.py"]
