#!/bin/bash
set -e

# Configuration
VENV_DIR="venv"
PYTHON="python3.11"
TTS_PORT=8001

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== NEURA TTS Local Service Setup ===${NC}"

# Check for system dependencies
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: ffmpeg is not installed. Run 'brew install ffmpeg' for better performance.${NC}"
fi

if ! command -v espeak-ng &> /dev/null; then
    echo -e "${YELLOW}Warning: espeak-ng is not installed. Run 'brew install espeak-ng' to avoid phonemizer errors.${NC}"
fi

# Change to script directory
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    $PYTHON -m venv $VENV_DIR
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

echo -e "${YELLOW}Updating Pip and Core Dependencies...${NC}"
pip install --upgrade pip setuptools wheel

# Install PyTorch (Stable 2.5.1)
echo -e "${YELLOW}Ensuring Stable PyTorch (2.5.1)...${NC}"
pip install torch==2.5.1 torchaudio==2.5.1 torchvision==0.20.1

# Install specific missing dependencies and known working versions
# Note: transformers is pinned to 4.41.2 because newer versions break TTS 0.22.0
echo -e "${YELLOW}Installing/Updating XTTS Dependencies...${NC}"
pip install \
    PyYAML \
    coqpit \
    trainer \
    hangul-romanize \
    pysbd \
    num2words \
    jieba \
    jamo \
    anyascii \
    gruut \
    unidecode \
    typing-extensions \
    pandas \
    matplotlib \
    scikit-learn \
    inflect \
    pypinyin \
    bangla \
    bnnumerizer \
    bnunicodenormalizer \
    g2pkk \
    mecab-python3 \
    unidic-lite \
    cython \
    "huggingface_hub<1.0" \
    safetensors \
    "tokenizers>=0.19,<0.20" \
    aiohttp \
    einops \
    encodec \
    flask \
    umap-learn \
    catalogue \
    cymem \
    murmurhash \
    preshed \
    spacy-legacy \
    spacy-loggers \
    srsly \
    "thinc<8.4.0" \
    wasabi \
    weasel \
    "spacy<3.8.0" \
    "transformers==4.41.2"

# Install remaining requirements
pip install -r requirements.txt --no-deps

# Manually ensure critical deps
pip install "numpy<2.0.0" scipy librosa soundfile tqdm structlog fastapi uvicorn python-multipart aiofiles redis protobuf

# Set environment variables
# We use CPU because MPS has multiple bugs with XTTS v2 (attention masks and channel limits)
export TTS_DEVICE="cpu"
export TTS_MODEL_PATH="$(pwd)/models"
export COQUI_TOS_AGREED=1

# Create directories
mkdir -p "$TTS_MODEL_PATH"
mkdir -p "$(pwd)/voices"

echo -e "${GREEN}=== Starting TTS Service on Port $TTS_PORT (CPU Stable Mode) ===${NC}"
echo -e "${YELLOW}Using CPU to ensure 100% stability and avoid MPS errors.${NC}"

uvicorn server:app --host 0.0.0.0 --port $TTS_PORT --reload
