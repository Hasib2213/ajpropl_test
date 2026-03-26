from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from config.database import connect_db, close_db
from config.settings import settings
from routers.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    print(f"\n {settings.APP_NAME} v{settings.APP_VERSION} is running\n")
    yield
    await close_db()


app = FastAPI(
    title="ResaleAI — Fashion AI Backend",
    description="""
## ResaleAI — AI-Powered Garment Processing

### Auto-generated listing:
- Product Title, Description
- Product Details & Metafields
- Tags, SKU, Variants
- Storage & Automation info
-features:physical_dimensions,background_removal,ai_virtual_tryon,image_diagram,mannequin,model

-feature_json:[{"features": ["background_removal", "model"]}, {"features": ["physical_dimensions", "virtual_tryon"]}]
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(products_router, prefix="/api/v1")


@app.get("/upload", tags=["Upload"])
async def upload_page():
    """
    Serve the multi-image upload interface.
    Navigate to http://localhost:8000/upload to use the upload form.
    """
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(static_dir, "upload.html"))


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "features": [
            "physical_dimensions",
            "background_removal",
            "ai_virtual_tryon",
            "image_diagram",
            "mannequin",
            "model",
        ],
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # Increased timeouts to support long-running AI processing requests
    # timeout-keep-alive: Keep connections alive during long processing (default 5s)
    # timeout-graceful-shutdown: Graceful shutdown timeout (default 15s)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        timeout_keep_alive=650,  # ~11 minutes for long client keep-alive windows
        timeout_graceful_shutdown=60,
    )