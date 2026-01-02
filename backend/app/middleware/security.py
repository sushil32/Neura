"""Security middleware and utilities."""
import re
from typing import List, Optional, Set

import structlog
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, validator
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(self), camera=()",
}

# Patterns for input validation
DANGEROUS_PATTERNS = [
    r"<script\b[^>]*>(.*?)</script>",  # Script tags
    r"javascript:",                      # JavaScript URLs
    r"on\w+\s*=",                        # Event handlers
    r"expression\s*\(",                  # CSS expressions
    r"url\s*\(\s*['\"]?\s*data:",       # Data URLs in CSS
]

# Compiled patterns
DANGEROUS_REGEX = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers and validation."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with security checks."""
        # Add security headers to response
        response = await call_next(request)
        
        for header, value in SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value
        
        return response


class InputValidator:
    """Utility for validating and sanitizing input."""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 10000) -> str:
        """
        Sanitize a string input.
        
        - Removes dangerous patterns
        - Limits length
        - Strips leading/trailing whitespace
        """
        if not value:
            return value
        
        # Limit length
        value = value[:max_length]
        
        # Strip whitespace
        value = value.strip()
        
        # Check for dangerous patterns
        for pattern in DANGEROUS_REGEX:
            if pattern.search(value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid input: potentially dangerous content detected",
                )
        
        return value
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """Remove HTML tags from string."""
        import html
        
        # Escape HTML entities
        value = html.escape(value)
        
        # Remove any remaining tags
        value = re.sub(r"<[^>]+>", "", value)
        
        return value
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_uuid(value: str) -> bool:
        """Validate UUID format."""
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(pattern, value, re.IGNORECASE))
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate and sanitize filename."""
        # Remove path components
        filename = filename.replace("\\", "/")
        filename = filename.split("/")[-1]
        
        # Remove dangerous characters
        filename = re.sub(r"[^\w\.\-]", "_", filename)
        
        # Prevent directory traversal
        if ".." in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename",
            )
        
        # Limit length
        max_length = 255
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        if len(filename) > max_length:
            name = name[:max_length - len(ext) - 1]
            filename = f"{name}.{ext}" if ext else name
        
        return filename


class SQLInjectionProtection:
    """Protection against SQL injection (extra layer beyond ORM)."""
    
    DANGEROUS_KEYWORDS = {
        "union", "select", "insert", "update", "delete", "drop",
        "truncate", "exec", "execute", "--", "/*", "*/"
    }
    
    @classmethod
    def check_input(cls, value: str) -> bool:
        """Check if input contains SQL injection patterns."""
        if not value:
            return True
        
        lower_value = value.lower()
        
        for keyword in cls.DANGEROUS_KEYWORDS:
            # Check for keyword with word boundaries
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, lower_value):
                return False
        
        return True
    
    @classmethod
    def sanitize(cls, value: str) -> str:
        """Sanitize input by removing dangerous SQL patterns."""
        if not value:
            return value
        
        for keyword in cls.DANGEROUS_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            value = re.sub(pattern, "", value, flags=re.IGNORECASE)
        
        return value


class RequestValidator(BaseModel):
    """Base class for request validation with security features."""
    
    class Config:
        # Strip whitespace from strings
        anystr_strip_whitespace = True
        # Limit string length
        max_anystr_length = 10000
    
    @validator("*", pre=True)
    def sanitize_strings(cls, v):
        """Sanitize all string inputs."""
        if isinstance(v, str):
            return InputValidator.sanitize_string(v)
        return v


def validate_content_type(
    request: Request,
    allowed_types: Set[str],
) -> None:
    """Validate request content type."""
    content_type = request.headers.get("content-type", "")
    
    # Extract main content type (ignore charset etc.)
    main_type = content_type.split(";")[0].strip().lower()
    
    if main_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content type '{content_type}' not allowed. Allowed: {allowed_types}",
        )


def validate_file_upload(
    filename: str,
    content_type: str,
    size: int,
    allowed_extensions: Set[str],
    allowed_content_types: Set[str],
    max_size: int,
) -> str:
    """
    Validate uploaded file.
    
    Returns sanitized filename.
    """
    # Validate extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '.{ext}' not allowed",
        )
    
    # Validate content type
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{content_type}' not allowed",
        )
    
    # Validate size
    if size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {max_size / (1024*1024):.1f}MB",
        )
    
    return InputValidator.validate_filename(filename)


# Allowed file types
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "flac"}
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/flac",
    "audio/x-wav", "audio/x-m4a",
}

ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "avi"}
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
}

