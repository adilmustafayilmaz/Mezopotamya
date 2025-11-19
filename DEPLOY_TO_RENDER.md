# Deploying to Render - Quick Guide

## The Issue You Encountered

Render is looking for a Dockerfile in the root directory, but this project has Dockerfiles in subdirectories. 

## Solution: Two Deployment Options

### Option 1: Use Blueprint Deployment (Recommended) ✅

This uses the `render.yaml` file for native Python/Node deployment (not Docker):

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Click "New +" → "Blueprint"**
3. **Connect your GitHub repository**
4. **Render will automatically detect `render.yaml`**
5. **Render will deploy backend and frontend as separate services**

This approach:
- ✅ Uses native Python/Node (faster builds)
- ✅ Automatically configures services
- ✅ Handles environment variables from `render.yaml`
- ✅ No Docker needed

**Important**: Make sure you:
- Update `render.yaml` with your actual Qdrant and Ollama URLs
- Set up environment variables in Render dashboard after deployment
- Use Qdrant Cloud (free tier) instead of self-hosting Qdrant

### Option 2: Manual Docker Deployment

If you prefer Docker deployment:

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Click "New +" → "Web Service"**
3. **Connect your GitHub repository**
4. **Configure the service**:
   - **Environment**: Docker
   - **Dockerfile Path**: `./Dockerfile` (root level)
   - **Docker Context**: `.` (root)
   - **Build Command**: (leave empty, Docker handles it)
   - **Start Command**: (leave empty, CMD in Dockerfile handles it)

5. **Set Environment Variables**:
   ```
   PORT=8000
   DATABASE_PATH=/opt/render/project/src/data/mezopotamya.db
   OLLAMA_HOST=https://your-ollama-service.com
   QDRANT_HOST=your-qdrant-cluster.qdrant.io
   QDRANT_PORT=6333
   QDRANT_API_KEY=your-api-key
   EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   CHUNK_SIZE=512
   CHUNK_OVERLAP=50
   ```

6. **Add Persistent Disk**:
   - Name: `mezopotamya-data`
   - Mount Path: `/opt/render/project/src/data`
   - Size: 1GB

## What I Fixed

1. ✅ Created root-level `Dockerfile` for Docker deployment
2. ✅ Updated `main.py` to use `PORT` environment variable (required by Render)
3. ✅ Commented out optional Qdrant service in `render.yaml` to avoid Docker issues

## Recommendation

**Use Option 1 (Blueprint)** - It's easier, faster, and designed for this project structure.

The Dockerfile in the root is now available as a fallback if you specifically need Docker deployment.

## Next Steps

1. Update `render.yaml` with your actual service URLs
2. Deploy using Blueprint method
3. Set environment variables in Render dashboard
4. Test the API at your Render URL

## Troubleshooting

- **Backend won't start**: Check PORT environment variable and database path
- **Can't connect to Qdrant**: Verify QDRANT_HOST and QDRANT_API_KEY
- **Can't connect to Ollama**: Verify OLLAMA_HOST URL is accessible

For more details, see `RENDER_DEPLOYMENT.md`
