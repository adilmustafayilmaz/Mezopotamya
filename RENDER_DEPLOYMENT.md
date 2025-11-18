# Deploying Mezopotamya.Travel to Render

## Overview

This guide explains how to deploy the Mezopotamya.Travel platform to Render. Since Render doesn't support docker-compose directly, services need to be deployed separately.

## Important Considerations

### Resource Requirements

1. **Ollama (LLM Service)**: 
   - Requires 8GB+ RAM for models
   - **Not recommended on Render free tier**
   - **Options**:
     - Use external Ollama service (separate VPS)
     - Use OpenAI/Anthropic API instead
     - Use Hugging Face Inference API
     - Deploy Ollama on a separate Render service (paid plan required)

2. **Qdrant (Vector Database)**:
   - Can be deployed on Render
   - **Better option**: Use [Qdrant Cloud](https://cloud.qdrant.io/) (free tier available)
   - Requires persistent disk storage

3. **Backend & Frontend**:
   - Can run on Render starter plan
   - Backend needs persistent disk for SQLite

## Deployment Options

### Option 1: Full Render Deployment (Recommended for Production)

#### Prerequisites
- Render account (free tier works for backend/frontend)
- Qdrant Cloud account (free tier available)
- External Ollama service OR use API-based LLM

#### Steps

1. **Set up Qdrant Cloud** (Recommended):
   - Sign up at https://cloud.qdrant.io/
   - Create a free cluster
   - Get cluster URL and API key
   - Update `QDRANT_HOST` in render.yaml

2. **Set up Ollama** (Choose one):
   - **Option A**: Deploy Ollama on separate VPS (DigitalOcean, Linode, etc.)
   - **Option B**: Use OpenAI API (modify code to use OpenAI instead)
   - **Option C**: Use Hugging Face Inference API
   - **Option D**: Deploy Ollama as Render service (requires paid plan)

3. **Deploy Backend**:
   ```bash
   # Connect your GitHub repo to Render
   # Render will auto-detect render.yaml or you can configure manually
   ```
   
   **Manual Configuration**:
   - Type: Web Service
   - Environment: Python 3
   - Build Command: `pip install -r mezopotamya-backend/requirements.txt`
   - Start Command: `cd mezopotamya-backend && python main.py`
   - Environment Variables:
     ```
     DATABASE_PATH=/opt/render/project/src/data/mezopotamya.db
     OLLAMA_HOST=https://your-ollama-service.com
     QDRANT_HOST=your-cluster.qdrant.io
     QDRANT_PORT=6333
     QDRANT_API_KEY=your-api-key
     EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
     CHUNK_SIZE=512
     CHUNK_OVERLAP=50
     PORT=8000
     ```
   - Add Disk: 1GB persistent disk at `/opt/render/project/src/data`

4. **Deploy Frontend**:
   - Type: Web Service
   - Environment: Node
   - Build Command: `cd mezopotamya-frontend && npm install && npm run build`
   - Start Command: `cd mezopotamya-frontend && npm start`
   - Environment Variables:
     ```
     NEXT_PUBLIC_API_URL=https://mezopotamya-backend.onrender.com
     PORT=3000
     NODE_ENV=production
     ```

5. **Deploy Qdrant** (Optional - if not using Qdrant Cloud):
   - Type: Web Service
   - Environment: Docker
   - Dockerfile Path: `./qdrant.Dockerfile`
   - Add Disk: 1GB persistent disk at `/qdrant/storage`

### Option 2: Simplified Deployment (Using External Services)

For easier deployment, use managed services:

1. **Qdrant**: Use Qdrant Cloud (free tier)
2. **LLM**: Use OpenAI API or Hugging Face
3. **Database**: Consider PostgreSQL (Render provides free PostgreSQL)

## Required Code Changes for Render

### 1. Update Qdrant Connection (if using Qdrant Cloud)

The current code should work, but you may need to add API key support:

```python
# In vector_store.py, update __init__:
def __init__(self, host: str = None, port: int = None, api_key: str = None, collection_name: str = "tourism_documents"):
    # ...
    if api_key:
        self.client = QdrantClient(url=f"https://{self.host}", api_key=api_key)
    else:
        self.client = QdrantClient(host=self.host, port=self.port)
```

### 2. Update Ollama Connection

If using external Ollama service, ensure the URL is accessible:

```python
# Already handled via OLLAMA_HOST env var
```

### 3. Database Path

SQLite path should use Render's disk mount:
```python
DATABASE_PATH=/opt/render/project/src/data/mezopotamya.db
```

## Environment Variables Summary

### Backend Service
```
DATABASE_PATH=/opt/render/project/src/data/mezopotamya.db
OLLAMA_HOST=https://your-ollama-service.com
QDRANT_HOST=your-cluster.qdrant.io
QDRANT_PORT=6333
QDRANT_API_KEY=your-api-key (if using Qdrant Cloud)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=50
PORT=8000
```

### Frontend Service
```
NEXT_PUBLIC_API_URL=https://mezopotamya-backend.onrender.com
PORT=3000
NODE_ENV=production
```

## Deployment Steps

1. **Push code to GitHub** (if not already done)

2. **Connect to Render**:
   - Go to https://dashboard.render.com
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Render will detect `render.yaml` automatically

3. **Or deploy manually**:
   - Create each service individually
   - Use the configurations above

4. **Set environment variables** in Render dashboard

5. **Add persistent disks** for backend (data) and Qdrant (if self-hosting)

6. **Deploy and test**

## Cost Considerations

- **Free Tier**: Backend + Frontend (with limitations)
- **Starter Plan ($7/month)**: Better performance, more resources
- **Qdrant Cloud**: Free tier available (1GB storage)
- **Ollama**: External VPS (~$5-10/month) or use API services

## Troubleshooting

### Backend won't start
- Check environment variables
- Verify Qdrant connection
- Check disk mount path

### Qdrant connection fails
- Verify QDRANT_HOST and QDRANT_PORT
- If using Qdrant Cloud, add API key
- Check network connectivity

### Ollama connection fails
- Verify OLLAMA_HOST URL is accessible
- Check if Ollama service is running
- Consider using API-based LLM instead

### Frontend can't connect to backend
- Verify NEXT_PUBLIC_API_URL
- Check CORS settings in backend
- Ensure backend is deployed and running

## Alternative: Use Render Blueprint

You can use the provided `render.yaml` as a blueprint:

1. Push code to GitHub
2. In Render: New → Blueprint
3. Connect repository
4. Render will auto-detect `render.yaml`
5. Review and deploy

## Next Steps

1. Set up Qdrant Cloud account
2. Decide on Ollama deployment strategy
3. Update environment variables
4. Deploy services
5. Test endpoints

## Support

For issues:
- Render Docs: https://render.com/docs
- Qdrant Cloud: https://cloud.qdrant.io/docs
- Check service logs in Render dashboard

