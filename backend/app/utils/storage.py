"""S3/MinIO storage utilities."""
import io
from typing import BinaryIO, Optional
from uuid import uuid4

import aioboto3
import structlog

from app.config import settings

logger = structlog.get_logger()


class StorageClient:
    """Async S3/MinIO storage client."""
    
    def __init__(self):
        self.session = aioboto3.Session()
        self.bucket = settings.s3_bucket
    
    def _get_client_config(self):
        return {
            "service_name": "s3",
            "endpoint_url": settings.s3_endpoint,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }
    
    async def upload_file(
        self,
        file: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to S3.
        
        Returns the URL of the uploaded file.
        """
        async with self.session.client(**self._get_client_config()) as s3:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            
            await s3.upload_fileobj(file, self.bucket, key, ExtraArgs=extra_args)
            
            logger.info("File uploaded", bucket=self.bucket, key=key)
            return f"{settings.s3_endpoint}/{self.bucket}/{key}"
    
    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload bytes to S3."""
        return await self.upload_file(io.BytesIO(data), key, content_type)
    
    async def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            data = await response["Body"].read()
            logger.info("File downloaded", bucket=self.bucket, key=key)
            return data
    
    async def delete_file(self, key: str) -> None:
        """Delete a file from S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)
            logger.info("File deleted", bucket=self.bucket, key=key)
    
    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for a file."""
        async with self.session.client(**self._get_client_config()) as s3:
            url = await s3.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
    
    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in S3."""
        async with self.session.client(**self._get_client_config()) as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False
    
    async def ensure_bucket_exists(self) -> None:
        """Create the bucket if it doesn't exist."""
        async with self.session.client(**self._get_client_config()) as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket)
            except Exception:
                await s3.create_bucket(Bucket=self.bucket)
                logger.info("Bucket created", bucket=self.bucket)
    
    @staticmethod
    def generate_key(prefix: str, filename: str, unique: bool = True) -> str:
        """Generate a storage key for a file."""
        if unique:
            unique_id = uuid4().hex[:8]
            return f"{prefix}/{unique_id}_{filename}"
        return f"{prefix}/{filename}"


# Global storage client instance
storage = StorageClient()

