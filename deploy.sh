#!/bin/bash
echo "Starting Orkestra Control Plane Deployment..."

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker daemon is not running. Please start Docker and try again."
  exit 1
fi

echo "Building and starting containers..."
docker compose up -d --build

echo "Deployment complete!"
echo "Access the Control Plane UI at: http://localhost:3000"
echo "API Server running internally at: http://localhost:8000"
