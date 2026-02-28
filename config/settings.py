from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ResaleAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "resale_ai"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # APIs
    REMOVEBG_API_KEY: str = ""
    REPLICATE_API_TOKEN: str = ""
    HUGGINGFACE_API_TOKEN: str = ""
    AI_PROVIDER: str = "HUGGINGFACE"  # REPLICATE or HUGGINGFACE
    GOOGLE_VISION_API_KEY: str = ""

    # Cloudflare R2
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "resale-ai-images"
    R2_ENDPOINT_URL: str = ""
    R2_PUBLIC_URL: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()