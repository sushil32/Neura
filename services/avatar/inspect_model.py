import torch
from pathlib import Path
import sys

def inspect_model(path):
    try:
        checkpoint = torch.load(path, map_location='cpu')
        print(f"Type: {type(checkpoint)}")
        if isinstance(checkpoint, dict):
            print(f"Keys: {list(checkpoint.keys())}")
            if 'state_dict' in checkpoint:
                sd = checkpoint['state_dict']
            else:
                sd = checkpoint
            
            print(f"First 10 State Dict Keys:")
            for k in list(sd.keys())[:10]:
                print(f"  {k}: {sd[k].shape}")
        else:
            print("Checkpoint is not a dict")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_model(sys.argv[1])
    else:
        print("Usage: python inspect_model.py <path>")
