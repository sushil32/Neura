#!/usr/bin/env python3
"""
Download SadTalker models from Hugging Face.
Alternative to GitHub releases which may have rate limits.
"""

import os
from pathlib import Path
from huggingface_hub import hf_hub_download

def download_sadtalker_from_hf():
    """Download SadTalker models from Hugging Face."""
    
    # Setup paths
    checkpoints_dir = Path(__file__).parent / "models" / "sadtalker" / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    print("📦 Downloading SadTalker models from Hugging Face...")
    print(f"📁 Destination: {checkpoints_dir}\n")
    
    # Models to download from HF
    models = [
        {
            "repo_id": "vinthony/SadTalker",
            "filename": "SadTalker_V0.0.2_256.safetensors",
            "subfolder": "checkpoints"
        },
        {
            "repo_id": "vinthony/SadTalker", 
            "filename": "SadTalker_V0.0.2_512.safetensors",
            "subfolder": "checkpoints"
        }
    ]
    
    for model_info in models:
        filename = model_info["filename"]
        dest_path = checkpoints_dir / filename
        
        if dest_path.exists():
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"✓ {filename} already exists ({size_mb:.1f} MB)")
            continue
        
        print(f"📥 Downloading {filename}...")
        try:
            downloaded_path = hf_hub_download(
                repo_id=model_info["repo_id"],
                filename=model_info["filename"],
                subfolder=model_info.get("subfolder"),
                cache_dir=str(checkpoints_dir.parent / "hf_cache"),
                local_dir=str(checkpoints_dir),
                local_dir_use_symlinks=False
            )
            
            # Check if file exists
            if Path(downloaded_path).exists() or dest_path.exists():
                size_mb = (Path(downloaded_path) if Path(downloaded_path).exists() else dest_path).stat().st_size / (1024 * 1024)
                print(f"✓ Downloaded {filename} ({size_mb:.1f} MB)\n")
            else:
                print(f"❌ Failed to download {filename}\n")
                
        except Exception as e:
            print(f"❌ Error downloading {filename}: {e}\n")
    
    print("\n🎉 Download complete!")
    print(f"📁 Models location: {checkpoints_dir}")

if __name__ == "__main__":
    try:
        download_sadtalker_from_hf()
    except ImportError:
        print("❌ huggingface_hub not installed")
        print("Install with: pip install huggingface_hub")
        exit(1)
