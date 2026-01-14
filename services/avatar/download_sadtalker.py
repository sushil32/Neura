#!/usr/bin/env python3
"""
Download SadTalker pre-trained models.

This script downloads all required model files for SadTalker avatar generation:
- Face reconstruction models
- Expression mapping models  
- Main SadTalker models (256x256 and 512x512)
- Face landmark detector

Total download size: ~2.5GB
"""

import os
import sys
from pathlib import Path
import urllib.request
import hashlib
from typing import Dict, Optional

# Model URLs and checksums
MODELS = {
    "mapping_00109-model.pth.tar": {
        "url": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/mapping_00109-model.pth.tar",
        "size_mb": 150,
        "md5": None  # Add if available
    },
    "mapping_00229-model.pth.tar": {
        "url": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/mapping_00229-model.pth.tar",
        "size_mb": 150,
        "md5": None
    },
    "SadTalker_V0.0.2_256.safetensors": {
        "url": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/SadTalker_V0.0.2_256.safetensors",
        "size_mb": 800,
        "md5": None
    },
    "SadTalker_V0.0.2_512.safetensors": {
        "url": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/SadTalker_V0.0.2_512.safetensors",
        "size_mb": 800,
        "md5": None
    },
    "shape_predictor_68_face_landmarks.dat": {
        "url": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/shape_predictor_68_face_landmarks.dat",
        "size_mb": 100,
        "md5": None
    },
}

class DownloadProgress:
    """Simple progress reporter for downloads."""
    
    def __init__(self, filename: str, total_size: int):
        self.filename = filename
        self.total_size = total_size
        self.downloaded = 0
        
    def __call__(self, block_num: int, block_size: int, total_size: int):
        self.downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, (self.downloaded / total_size) * 100)
            mb_downloaded = self.downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            
            # Print progress bar
            bar_length = 40
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f"\r{self.filename}: [{bar}] {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='', flush=True)

def verify_checksum(filepath: Path, expected_md5: Optional[str]) -> bool:
    """Verify file MD5 checksum if provided."""
    if not expected_md5:
        return True
        
    print(f"  Verifying checksum...")
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            md5.update(chunk)
    
    actual_md5 = md5.hexdigest()
    if actual_md5 != expected_md5:
        print(f"  ❌ Checksum mismatch! Expected {expected_md5}, got {actual_md5}")
        return False
    
    print(f"  ✓ Checksum verified")
    return True

def download_model(name: str, info: Dict, dest_dir: Path) -> bool:
    """Download a single model file."""
    dest_path = dest_dir / name
    
    # Check if already exists
    if dest_path.exists():
        file_size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"✓ {name} already exists ({file_size_mb:.1f} MB)")
        
        # Verify checksum if provided
        if info.get("md5"):
            if not verify_checksum(dest_path, info["md5"]):
                print(f"  Re-downloading due to checksum mismatch...")
                dest_path.unlink()
            else:
                return True
        return True
    
    # Download
    print(f"\n📥 Downloading {name} (~{info['size_mb']} MB)...")
    try:
        urllib.request.urlretrieve(
            info["url"],
            dest_path,
            reporthook=DownloadProgress(name, info['size_mb'] * 1024 * 1024)
        )
        print()  # New line after progress bar
        
        # Verify checksum
        if info.get("md5"):
            if not verify_checksum(dest_path, info["md5"]):
                dest_path.unlink()
                return False
        
        file_size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"✓ Downloaded {name} ({file_size_mb:.1f} MB)")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to download {name}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False

def main():
    """Download all SadTalker models."""
    print("=" * 60)
    print("SadTalker Model Downloader")
    print("=" * 60)
    
    # Setup directories
    script_dir = Path(__file__).parent
    checkpoints_dir = script_dir / "models" / "sadtalker" / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Download directory: {checkpoints_dir}")
    print(f"📦 Total models: {len(MODELS)}")
    
    total_size_mb = sum(m["size_mb"] for m in MODELS.values())
    print(f"💾 Total download size: ~{total_size_mb} MB (~{total_size_mb/1024:.1f} GB)")
    
    # Ask for confirmation
    response = input("\n⚠️  This will download ~2.5GB of data. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return 1
    
    # Download each model
    print("\n" + "=" * 60)
    success_count = 0
    failed_models = []
    
    for name, info in MODELS.items():
        if download_model(name, info, checkpoints_dir):
            success_count += 1
        else:
            failed_models.append(name)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"✓ Successfully downloaded: {success_count}/{len(MODELS)} models")
    
    if failed_models:
        print(f"\n❌ Failed downloads:")
        for name in failed_models:
            print(f"  - {name}")
        return 1
    
    print("\n🎉 All models downloaded successfully!")
    print(f"📁 Models location: {checkpoints_dir}")
    print("\nNext steps:")
    print("  1. Update requirements.txt with SadTalker dependencies")
    print("  2. Implement SadTalkerRenderer class")
    print("  3. Integrate with avatar service")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
