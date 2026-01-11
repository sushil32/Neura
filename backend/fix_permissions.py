import boto3
import json
import logging
import sys
from botocore.client import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try internal docker service name first
ENDPOINTS = [
    "http://minio:9000",
    "http://localhost:9000",
]

ACCESS_KEY = "neura_minio"
SECRET_KEY = "neura_minio_password"
REGION = "us-east-1"
BUCKETS_MAP = {
    "videos": "neura-videos",
    "avatars": "neura-avatars",
    "voices": "neura-voices",
    "thumbnails": "neura-thumbnails"
}

def get_working_client():
    for endpoint in ENDPOINTS:
        try:
            logger.info(f"Trying S3 endpoint: {endpoint}")
            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                region_name=REGION,
                config=Config(signature_version="s3v4", connect_timeout=2, read_timeout=2)
            )
            # Test connection
            client.list_buckets()
            logger.info(f"Connected to {endpoint}")
            return client
        except Exception as e:
            logger.warning(f"Failed to connect to {endpoint}: {e}")
    return None

def fix_permissions():
    s3 = get_working_client()
    if not s3:
        logger.error("Could not connect to any S3 endpoint.")
        sys.exit(1)

    for name, bucket_name in BUCKETS_MAP.items():
        logger.info(f"Processing bucket: {bucket_name}")
        
        # 1. Bucket Policy
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }]
        }
        try:
            s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
            logger.info("  ✅ Policy updated.")
        except Exception as e:
            logger.error(f"  ❌ Policy update failed: {e}")

        # 2. Object ACLs
        try:
            objects = s3.list_objects_v2(Bucket=bucket_name)
            if "Contents" in objects:
                count = 0
                for obj in objects["Contents"]:
                    key = obj["Key"]
                    try:
                        s3.put_object_acl(Bucket=bucket_name, Key=key, ACL="public-read")
                        count += 1
                    except Exception as e:
                        logger.error(f"  ❌ ACL update failed for {key}: {e}")
                logger.info(f"  ✅ ACL updated for {count} objects.")
            else:
                logger.info("  (Bucket is empty)")
        except Exception as e:
            logger.error(f"  Lists objects failed: {e}")

if __name__ == "__main__":
    fix_permissions()
