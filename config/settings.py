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
    REPLICATE_MAX_RETRIES: int = 3
    REPLICATE_MAX_CONCURRENT: int = 1
    REPLICATE_MIN_INTERVAL_SECONDS: float = 1.2
    REPLICATE_BACKOFF_BASE_SECONDS: float = 2.0
    REPLICATE_BACKOFF_MAX_SECONDS: float = 12.0
    HUGGINGFACE_API_TOKEN: str = ""
    AI_PROVIDER: str = "HUGGINGFACE"  # REPLICATE, HUGGINGFACE, or NANO_BANANA_PRO
    NANO_BANANA_PRO_API_KEY: str = ""
    NANO_BANANA_PRO_BASE_URL: str = ""
    NANO_BANANA_PRO_ENDPOINT_PATH: str = "/generate"
    NANO_BANANA_PRO_MODEL: str = "nano-banana-pro-preview"
    NANO_BANANA_PRO_TIMEOUT_SECONDS: int = 120
    NANO_BANANA_FEMALE_MODEL_URLS: str = ""
    NANO_BANANA_MALE_MODEL_URLS: str = ""
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