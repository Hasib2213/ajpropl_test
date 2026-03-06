# Docker Build Guide

## Multi-Stage Docker Build

This project uses a **multi-stage Docker build** to create an optimized, lean production image.

### Build Stages

#### Stage 1: Builder
- Base: `python:3.11-slim`
- Installs all build dependencies (gcc, g++, development libraries)
- Creates Python virtual environment
- Installs all Python packages from `requirements.txt`
- **Not included in final image** - reduces image size

#### Stage 2: Runtime
- Base: `python:3.11-slim`
- Installs only runtime dependencies (libraries needed at runtime)
- Copies virtual environment from builder stage
- Copies application code
- Creates non-root user for security
- Ready for production

### Benefits

✅ **Smaller Image Size** - Removes build tools, saves ~500MB+
✅ **Faster Deployments** - Less to download and run
✅ **Better Security** - Non-root user, minimal dependencies
✅ **Cleaner Cache** - Build dependencies don't clutter layers

---

## Building the Docker Image

### Option 1: Using Dockerfile directly

```bash
# Build the image
docker build -t ajpropl-ai:latest .

# Run the container (requires external MongoDB & Redis)
docker run -p 8000:8000 \
  -e MONGODB_URL=mongodb://user:pass@host:27017/db \
  -e REDIS_URL=redis://host:6379 \
  ajpropl-ai:latest
```

### Option 2: Using Docker Compose (Recommended)

Complete setup with MongoDB, Redis, and the app:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# MongoDB
MONGODB_URL=mongodb://admin:password@mongodb:27017/ajpropl?authSource=admin

# Redis
REDIS_URL=redis://redis:6379

# Gemini API (if using AI features)
GEMINI_API_KEY=your_api_key_here


# Replicate API (for virtual try-on, mannequin, model)
REPLICATE_API_TOKEN=your_token_here
```

---

## Health Check

The container includes a health check that pings the `/health` endpoint every 30 seconds:

```yaml
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3
```

Check health status:
```bash
docker ps  # Look for "healthy" or "unhealthy" status
```

---

## Performance Tips

### For Development
```bash
# Keep volumes mounted for hot reloading
docker-compose up
```

### For Production
```bash
# Remove development volumes
docker-compose -f docker-compose.yml up -d
```

### Build Optimization

```bash
# Build without cache (full rebuild)
docker build --no-cache -t ajpropl-ai:latest .

# Build with specific target (debug only)
docker build --target builder -t ajpropl-ai:builder .
```

---

## Troubleshooting

### Image too large?
- Check `.dockerignore` for unnecessary files
- Verify Python dependencies in `requirements.txt` are minimal

### Dependencies missing at runtime?
- Add runtime libraries in Stage 2's `apt-get install`
- Don't remove build dependencies if needed at runtime

### Slow builds?
- Use Docker BuildKit: `DOCKER_BUILDKIT=1 docker build .`
- Cache dependencies by building in order

---

## Image Size Comparison

**Before Multi-Stage:** ~1.5 GB
**After Multi-Stage:** ~800 MB

Typical breakdown:
- Python base image: 150 MB
- Application + dependencies: 500 MB
- Runtime libraries: 150 MB

---

## Pushing to Registry

```bash
# Tag for registry
docker tag ajpropl-ai:latest myregistry.azurecr.io/ajpropl-ai:latest

# Push to Azure Container Registry
docker push myregistry.azurecr.io/ajpropl-ai:latest

# Pull from registry
docker pull myregistry.azurecr.io/ajpropl-ai:latest
```

---

## Next Steps

1. ✅ Verify Dockerfile works: `docker build -t ajpropl-ai:test .`
2. ✅ Test with compose: `docker-compose up`
3. ✅ Add production environment variables
4. ✅ Push to container registry
5. ✅ Deploy to container orchestration platform (Kubernetes, Azure Container Instances, etc.)
