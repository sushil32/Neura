#!/bin/bash
# Quick download script for SadTalker models
# Run this from the services/avatar directory

set -e

CHECKPOINTS_DIR="models/sadtalker/checkpoints"
mkdir -p "$CHECKPOINTS_DIR"

echo "📦 Downloading SadTalker models..."
echo "📁 Destination: $CHECKPOINTS_DIR"
echo ""

cd "$CHECKPOINTS_DIR"

# Download 256 model
if [ ! -f "SadTalker_V0.0.2_256.safetensors" ]; then
    echo "📥 Downloading SadTalker_V0.0.2_256.safetensors (~800MB)..."
    curl -L -o SadTalker_V0.0.2_256.safetensors \
        "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors"
    echo "✅ Downloaded 256 model"
else
    echo "✓ SadTalker_V0.0.2_256.safetensors already exists"
fi

echo ""

# Download 512 model
if [ ! -f "SadTalker_V0.0.2_512.safetensors" ]; then
    echo "📥 Downloading SadTalker_V0.0.2_512.safetensors (~800MB)..."
    curl -L -o SadTalker_V0.0.2_512.safetensors \
        "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors"
    echo "✅ Downloaded 512 model"
else
    echo "✓ SadTalker_V0.0.2_512.safetensors already exists"
fi

echo ""
echo "🎉 Download complete!"
echo ""
echo "Verifying files..."
ls -lh *.safetensors 2>/dev/null || echo "No safetensors files found"
