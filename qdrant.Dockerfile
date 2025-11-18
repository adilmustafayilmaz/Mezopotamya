# Qdrant Dockerfile for Render
FROM qdrant/qdrant:latest

# Qdrant will use the default configuration
# Storage will be mounted at /qdrant/storage

EXPOSE 6333 6334

