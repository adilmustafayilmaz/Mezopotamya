# Root Dockerfile for Backend Deployment on Render
# This is for Docker-based deployment. For native Python deployment, use render.yaml

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY mezopotamya-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mezopotamya-backend/ .

# Create data directory
RUN mkdir -p /app/data

# Use PORT environment variable for Render, default to 8000
ENV PORT=8000

# Expose port
EXPOSE $PORT

# Run the application
# Render sets PORT environment variable automatically
CMD python main.py
