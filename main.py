from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.database import connect_db, close_db
from config.settings import settings
from routers.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    print(f"\n🚀 {settings.APP_NAME} v{settings.APP_VERSION} is running\n")
    yield
    await close_db()


app = FastAPI(
    title="ResaleAI — Fashion AI Backend",
    description="""
## ResaleAI — AI-Powered Garment Processing

Upload a garment photo → AI handles the rest.

### 6 AI Features:
| # | Feature | API Used |
|---|---------|----------|
| 1 | **Physical Dimensions** | Gemini Vision |
| 2 | **Background Removal** | Remove.bg |
| 3 | **AI Virtual Try-On** | Replicate (IDM-VTON) |
| 4 | **Image Diagram** | Gemini Vision + Pillow |
| 5 | **Mannequin** | Replicate (SDXL) |
| 6 | **Model** | Replicate (IDM-VTON) |

### Auto-generated listing:
- Product Title, Description
- Product Details & Metafields
- Tags, SKU, Variants
- Storage & Automation info
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

app.include_router(products_router, prefix="/api/v1")


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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)