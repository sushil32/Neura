#!/bin/bash

export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1
# Configuration for Local MPS Execution
# =====================================

# 1. Project Root & Python Path
# Assumes script is run from services/avatar directory or project root
# We need to find the project root to set SHARED_PATH correctly
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# 2. Environment Variables
export PYTHONPATH=$SCRIPT_DIR
export AVATAR_MODEL_PATH="$SCRIPT_DIR/models"
export SHARED_PATH="$PROJECT_ROOT/shared"
export AVATAR_PATH="$SCRIPT_DIR/avatars"
export AVATAR_DEVICE="mps"  # Enable Metal Performance Shaders (Apple Silicon)

# 3. Create Shared & Avatar Directories if missing
if [ ! -d "$SHARED_PATH" ]; then
    echo "Creating shared directory at $SHARED_PATH"
    mkdir -p "$SHARED_PATH"
fi

if [ ! -d "$AVATAR_PATH" ]; then
    echo "Creating avatars directory at $AVATAR_PATH"
    mkdir -p "$AVATAR_PATH"
fi

# 4. Check Dependencies (Simplified check)
if ! python3 -c "import torch; print(f'Torch: {torch.__version__}, MPS Available: {torch.backends.mps.is_available()}')" &> /dev/null; then
    echo "⚠️  Validation Warning: PyTorch with MPS support might not be installed."
    echo "Please ensure you have installed requirements: pip install -r requirements.txt"
fi

echo "🚀 Starting Avatar Service Locally on MPS..."
echo "   - Model Path: $AVATAR_MODEL_PATH"
echo "   - Shared Path: $SHARED_PATH"
echo "   - Device: $AVATAR_DEVICE"
echo ""

# 5. Run Server
# We use uvicorn directly
cd "$SCRIPT_DIR"
python3 -m uvicorn server:app --host 0.0.0.0 --port 8002 --reload
