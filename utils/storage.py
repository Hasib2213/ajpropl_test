import uuid
from datetime import datetime
from config.database import db


class StorageService:
    """
    Storage Service - MongoDB Only
    
    All files stored in: resale_ai.files collection
    File references use: mongodb://file-id format
    """
    
    async def upload(self, file_bytes: bytes, folder: str, ext: str = "png", content_type: str = "image/png") -> str:
        """
        Store file in MongoDB and return reference URL
        
        Args:
            file_bytes: Raw image/file bytes
            folder: Storage folder (originals, bg_removed, tryons, mannequins, models, diagrams)
            ext: File extension (jpg, png, gif, etc)
            content_type: MIME type (image/jpeg, image/png, etc)
        
        Returns:
            Reference URL: mongodb://file-id
        """
        file_id = str(uuid.uuid4())
        database = db()
        files_collection = database["files"]
        
        file_doc = {
            "_id": file_id,
            "folder": folder,
            "ext": ext,
            "content_type": content_type,
            "data": file_bytes,
            "size": len(file_bytes),
            "uploaded_at": datetime.utcnow(),
        }
        await files_collection.insert_one(file_doc)
        
        return f"mongodb://{file_id}"
    
    async def get_file(self, file_id: str) -> bytes:
        """
        Retrieve file bytes from MongoDB by ID
        
        Args:
            file_id: File ID (from mongodb://file-id URL)
        
        Returns:
            File bytes (binary data)
        """
        database = db()
        files_collection = database["files"]
        file_doc = await files_collection.find_one({"_id": file_id})
        
        if not file_doc:
            raise FileNotFoundError(f"File {file_id} not found in MongoDB")
        
        return file_doc["data"]
    
    async def delete(self, file_id: str):
        """
        Delete file from MongoDB by ID
        
        Args:
            file_id: File ID to delete
        """
        database = db()
        files_collection = database["files"]
        await files_collection.delete_one({"_id": file_id})


storage = StorageService()
