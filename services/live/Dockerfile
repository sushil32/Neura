FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for aiortc (ffmpeg, libav, etc.)
RUN apt-get update && apt-get install -y \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    libsrtp2-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy logic
COPY . .

# Expose port (Signaling happens via Backend, but we might expose HTTP for health/direct)
EXPOSE 8003

# Run service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
