from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    print(f"✅ MongoDB connected → {settings.MONGODB_DB_NAME}")


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return client[settings.MONGODB_DB_NAME]


def db():
    """Get database instance for use in services"""
    return get_db()


# Collections
def col_products():
    return get_db()["products"]


def col_jobs():
    return get_db()["processing_jobs"]