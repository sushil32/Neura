# Avatar Service Dockerfile with Wav2Lip support
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies in stages to reduce I/O pressure
# Stage 1: Update package lists with retry
RUN apt-get update || apt-get update || apt-get update

# Stage 2: Install essential packages first
RUN apt-get install -y --no-install-recommends --fix-missing \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* || true

# Stage 3: Install X11 and graphics libraries (required for rendering)
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/* || true

# Stage 4: Install OpenGL libraries (try libgl1, fallback to alternatives)
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    libgl1 \
    || apt-get install -y --no-install-recommends --fix-missing \
    libgl1-mesa-glx \
    || apt-get install -y --no-install-recommends --fix-missing \
    libgl1-mesa-dri \
    || echo "OpenGL libraries optional - continuing without" \
    && rm -rf /var/lib/apt/lists/* || true

# Stage 5: Install ffmpeg and video processing tools
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* || true

# Final cleanup
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* || true

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PATCH: Fix basicsr incompatibility with torchvision 0.15+
# basicsr imports 'functional_tensor' which was removed. We redirect it to 'functional'
RUN sed -i 's/from torchvision.transforms.functional_tensor import rgb_to_grayscale/from torchvision.transforms.functional import rgb_to_grayscale/g' /usr/local/lib/python3.10/site-packages/basicsr/data/degradations.py || true

# Copy application code
COPY . .

# Create directories for models and avatars
RUN mkdir -p /app/models /app/avatars /app/temp

EXPOSE 8002

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]

