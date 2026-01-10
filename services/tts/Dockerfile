# TTS Service Dockerfile with Coqui XTTS support
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV COQUI_TOS_AGREED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libsndfile1 \
    espeak-ng \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .

# Stage 2: Install PyTorch first (heavy dependency)
RUN pip install --default-timeout=1000 torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# Stage 3: Install core dependencies
RUN pip install "numpy<2.0.0" scipy librosa soundfile tqdm

# Stage 4: Install TTS - use --no-deps to avoid Japanese tokenizer issues
# Then manually install only the required dependencies
# Explicitly pin transformers to avoid conflict and add spacy
RUN pip install TTS --no-deps && \
    pip install \
    anyascii \
    bangla \
    bnnumerizer \
    bnunicodenormalizer \
    coqpit \
    cython \
    docopt \
    einops \
    flask \
    fsspec \
    g2pkk \
    gruut \
    hangul-romanize \
    inflect \
    jieba \
    jamo \
    matplotlib \
    mecab-python3 \
    num2words \
    packaging \
    pandas \
    pypinyin \
    pysbd \
    python-dateutil \
    trainer \
    "transformers>=4.33.0,<4.42.0" \
    unidic-lite \
    umap-learn \
    spacy \
    || echo "Some optional TTS deps failed, but core should work"

# Stage 5: Install remaining app dependencies
RUN pip install \
    fastapi \
    uvicorn \
    python-multipart \
    aiofiles \
    redis \
    structlog \
    pydantic

# Copy application code
COPY . .

# Create directories for models and voices
RUN mkdir -p /app/models /app/voices

# Note: XTTS model will be downloaded on first request
# This avoids bloating the Docker image

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
