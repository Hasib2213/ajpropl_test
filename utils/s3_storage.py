"""
S3 Storage Utility - Upload images to AWS S3 and return URLs for database
Images stored in S3, only URLs stored in MongoDB
"""

import os
import boto3
from typing import Optional, Tuple
from datetime import datetime
import uuid
import mimetypes


class S3Storage:
    """Handle image uploads to AWS S3 bucket"""
    
    def __init__(self):
        self.access_key = os.getenv("S3_ACCESS_KEY")
        self.secret_key = os.getenv("S3_SECRET_KEY")
        self.region = os.getenv("S3_REGION", "us-east-1")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.endpoint_url = os.getenv("S3_ENDPOINT")
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            endpoint_url=self.endpoint_url
        )
    
    def upload_image(
        self, 
        image_bytes: bytes, 
        filename: str = None,
        folder: str = "images"
    ) -> str:
        """
        Upload image to S3 and return public URL
        
        Args:
            image_bytes: Image file content
            filename: Original filename (auto-generated if not provided)
            folder: S3 folder path (e.g., "images", "processed/background_removed")
        
        Returns:
            S3 object URL for database storage
            Example: https://s3.eu-north-1.amazonaws.com/bucket/images/uuid.jpg
        """
        if not filename:
            filename = f"{uuid.uuid4().hex}.jpg"
        
        # Generate key path
        key = f"{folder}/{datetime.now().strftime('%Y/%m/%d')}/{filename}"
        
        try:
            # Upload to S3
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_bytes,
                ContentType=content_type
            )
            
            # Generate URL
            url = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{key}"
            print(f"✓ Image uploaded to S3: {url}")
            return url
            
        except Exception as e:
            print(f"✗ S3 Upload failed: {str(e)}")
            raise
    
    def upload_image_file(
        self,
        file_path: str,
        folder: str = "images"
    ) -> str:
        """
        Upload image file from local path to S3
        
        Args:
            file_path: Path to image file
            folder: S3 folder path
        
        Returns:
            S3 object URL
        """
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        
        filename = os.path.basename(file_path)
        return self.upload_image(image_bytes, filename, folder)
    
    def get_public_url(self, key: str) -> str:
        """
        Generate public URL for S3 object
        
        Args:
            key: S3 object key (path)
        
        Returns:
            Public URL
        """
        return f"{self.endpoint_url}/{self.bucket_name}/{key}"
    
    def delete_image(self, key: str) -> bool:
        """
        Delete image from S3
        
        Args:
            key: S3 object key
        
        Returns:
            True if deleted, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            print(f"✓ Deleted from S3: {key}")
            return True
        except Exception as e:
            print(f"✗ S3 delete failed: {str(e)}")
            return False


# Singleton instance
_s3_storage = None

def get_s3_storage() -> S3Storage:
    """Get or create S3 storage instance"""
    global _s3_storage
    if _s3_storage is None:
        _s3_storage = S3Storage()
    return _s3_storage
