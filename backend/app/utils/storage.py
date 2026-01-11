"""S3/MinIO storage utilities."""
import io
import mimetypes
import os
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional
from uuid import uuid4

import aioboto3
import structlog
from botocore.config import Config

from app.config import settings

logger = structlog.get_logger()

# Bucket names for different content types
BUCKETS = {
    "videos": "neura-videos",
    "audio": "neura-audio",
    "avatars": "neura-avatars",
    "voices": "neura-voices",
    "thumbnails": "neura-thumbnails",
    "temp": "neura-temp",
}


class StorageClient:
    """Async S3/MinIO storage client with full feature support."""
    
    def __init__(self):
        self.session = aioboto3.Session()
        self.default_bucket = settings.s3_bucket
        self._buckets_ensured = False
    
    def _get_client_config(self) -> Dict:
        """Get S3 client configuration."""
        return {
            "service_name": "s3",
            "endpoint_url": settings.s3_endpoint,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        }
    
    async def ensure_buckets(self) -> None:
        """Ensure all required buckets exist."""
        if self._buckets_ensured:
            return
        
        async with self.session.client(**self._get_client_config()) as s3:
            for name, bucket in BUCKETS.items():
                try:
                    await s3.head_bucket(Bucket=bucket)
                    logger.debug(f"Bucket {bucket} exists")
                except Exception:
                    try:
                        await s3.create_bucket(Bucket=bucket)
                        logger.info(f"Created bucket: {bucket}")
                        
                        # Set bucket policy for public read (videos/thumbnails/avatars/voices)
                        if name in ["videos", "thumbnails", "avatars", "voices"]:
                            policy = {
                                "Version": "2012-10-17",
                                "Statement": [{
                                    "Effect": "Allow",
                                    "Principal": "*",
                                    "Action": ["s3:GetObject"],
                                    "Resource": [f"arn:aws:s3:::{bucket}/*"]
                                }]
                            }
                            import json
                            await s3.put_bucket_policy(
                                Bucket=bucket,
                                Policy=json.dumps(policy)
                            )
                    except Exception as e:
                        logger.warning(f"Could not create bucket {bucket}: {e}")
        
        self._buckets_ensured = True
    
    async def upload_file(
        self,
        file_path: str,
        bucket: str,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file from disk to S3.
        
        Args:
            file_path: Local file path
            bucket: Target bucket name
            key: Object key in bucket
            content_type: MIME type (auto-detected if not provided)
        
        Returns:
            Public URL of the uploaded file
        """
        await self.ensure_buckets()
        
        # Auto-detect content type
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            content_type = content_type or "application/octet-stream"
        
        async with self.session.client(**self._get_client_config()) as s3:
            with open(file_path, "rb") as f:
                await s3.upload_fileobj(
                    f,
                    bucket,
                    key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "ACL": "public-read" if bucket in [BUCKETS["videos"], BUCKETS["thumbnails"], BUCKETS["avatars"], BUCKETS["voices"]] else "private",
                    }
                )
            
            logger.info("File uploaded", bucket=bucket, key=key, content_type=content_type)
            
            # Return public URL
            return self._get_public_url(bucket, key)
    
    async def upload_fileobj(
        self,
        file: BinaryIO,
        bucket: str,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file object to S3."""
        await self.ensure_buckets()
        
        async with self.session.client(**self._get_client_config()) as s3:
            extra_args = {"ContentType": content_type} if content_type else {}
            
            await s3.upload_fileobj(file, bucket, key, ExtraArgs=extra_args)
            
            logger.info("File uploaded", bucket=bucket, key=key)
            return self._get_public_url(bucket, key)
    
    async def upload_bytes(
        self,
        data: bytes,
        bucket: str,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload bytes to S3."""
        return await self.upload_fileobj(io.BytesIO(data), bucket, key, content_type)
    
    async def download_file(
        self,
        bucket: str,
        key: str,
        destination: Optional[str] = None,
    ) -> bytes:
        """
        Download a file from S3.
        
        Args:
            bucket: Source bucket
            key: Object key
            destination: Optional local file path to save to
        
        Returns:
            File contents as bytes
        """
        async with self.session.client(**self._get_client_config()) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            data = await response["Body"].read()
            
            if destination:
                Path(destination).parent.mkdir(parents=True, exist_ok=True)
                Path(destination).write_bytes(data)
            
            logger.info("File downloaded", bucket=bucket, key=key)
            return data
    
    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file from S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            await s3.delete_object(Bucket=bucket, Key=key)
            logger.info("File deleted", bucket=bucket, key=key)
    
    async def delete_files(self, bucket: str, keys: List[str]) -> None:
        """Delete multiple files from S3."""
        if not keys:
            return
        
        async with self.session.client(**self._get_client_config()) as s3:
            objects = [{"Key": key} for key in keys]
            await s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects}
            )
            logger.info(f"Deleted {len(keys)} files from {bucket}")
    
    async def get_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate a presigned URL for a file.
        
        Args:
            bucket: Bucket name
            key: Object key
            expires_in: URL expiration in seconds (default 1 hour)
            method: S3 method (get_object, put_object)
        
        Returns:
            Presigned URL
        """
        async with self.session.client(**self._get_client_config()) as s3:
            url = await s3.generate_presigned_url(
                method,
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
    
    async def get_presigned_upload_url(
        self,
        bucket: str,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> Dict[str, str]:
        """
        Generate a presigned URL for uploading.
        
        Returns:
            Dictionary with 'url' and 'fields' for form upload
        """
        async with self.session.client(**self._get_client_config()) as s3:
            result = await s3.generate_presigned_post(
                Bucket=bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, 500 * 1024 * 1024],  # 500MB max
                ],
                ExpiresIn=expires_in,
            )
            return result
    
    async def file_exists(self, bucket: str, key: str) -> bool:
        """Check if a file exists in S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            try:
                await s3.head_object(Bucket=bucket, Key=key)
                return True
            except Exception:
                return False
    
    async def get_file_info(self, bucket: str, key: str) -> Optional[Dict]:
        """Get file metadata."""
        async with self.session.client(**self._get_client_config()) as s3:
            try:
                response = await s3.head_object(Bucket=bucket, Key=key)
                return {
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType"),
                    "last_modified": response["LastModified"],
                    "etag": response["ETag"],
                }
            except Exception:
                return None
    
    async def list_files(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[Dict]:
        """List files in a bucket with optional prefix."""
        async with self.session.client(**self._get_client_config()) as s3:
            response = await s3.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                }
                for obj in response.get("Contents", [])
            ]
    
    async def copy_file(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> str:
        """Copy a file within S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            await s3.copy_object(
                Bucket=dest_bucket,
                Key=dest_key,
                CopySource={"Bucket": source_bucket, "Key": source_key},
            )
            return self._get_public_url(dest_bucket, dest_key)
    
    def _get_public_url(self, bucket: str, key: str) -> str:
        """Get the public URL for an object."""
        # Use public endpoint for frontend access, fallback to internal endpoint
        endpoint = getattr(settings, 's3_public_endpoint', settings.s3_endpoint).rstrip("/")
        return f"{endpoint}/{bucket}/{key}"
    
    @staticmethod
    def generate_key(
        prefix: str,
        filename: str,
        unique: bool = True,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Generate a storage key for a file.
        
        Args:
            prefix: Key prefix (e.g., 'videos', 'audio')
            filename: Original filename
            unique: Add unique ID to prevent collisions
            user_id: Optional user ID for organization
        
        Returns:
            Storage key
        """
        # Clean filename
        safe_filename = "".join(
            c if c.isalnum() or c in ".-_" else "_"
            for c in filename
        )
        
        parts = [prefix]
        if user_id:
            parts.append(user_id)
        
        if unique:
            unique_id = uuid4().hex[:8]
            parts.append(f"{unique_id}_{safe_filename}")
        else:
            parts.append(safe_filename)
        
        return "/".join(parts)
    
    @staticmethod
    def get_bucket_for_type(file_type: str) -> str:
        """Get the appropriate bucket for a file type."""
        return BUCKETS.get(file_type, BUCKETS["temp"])


# Global storage client instance
storage_client = StorageClient()

# Backward compatibility
storage = storage_client
