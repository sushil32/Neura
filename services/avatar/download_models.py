import os
import urllib.request
import ssl
import sys

# Fix SSL context for Mac
ssl._create_default_https_context = ssl._create_unverified_context

# List of URLs to try
MODEL_URLS = [
    "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth",
    "https://huggingface.co/gvecchio/Wav2Lip-GAN/resolve/main/wav2lip_gan.pth",
    "https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth"
]

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "wav2lip_gan.pth")
AVATARS_DIR = os.path.join(os.path.dirname(__file__), "avatars")

def download_model():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        print(f"Created directory: {MODEL_DIR}")
        
    if not os.path.exists(AVATARS_DIR):
        os.makedirs(AVATARS_DIR)
        print(f"Created directory: {AVATARS_DIR}")

    if os.path.exists(MODEL_PATH):
        # Check size to ensure it's not a corrupted 404 file
        if os.path.getsize(MODEL_PATH) > 1000:
            print(f"Model already exists at {MODEL_PATH}")
            return
        else:
            print("Existing model file is too small (likely invalid), re-downloading...")
            os.remove(MODEL_PATH)

    print(f"Attempting to download Wav2Lip model...")
    
    success = False
    for url in MODEL_URLS:
        print(f"Trying {url}...")
        try:
            def progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    sys.stdout.write(f"\rDownloading: {percent}% ({total_size // 1024 // 1024} MB)")
                    sys.stdout.flush()

            urllib.request.urlretrieve(url, MODEL_PATH, reporthook=progress)
            
            # Verify file size (should be > 400MB)
            size = os.path.getsize(MODEL_PATH)
            if size > 1000000: # 1MB at least
                print(f"\nDownload complete! Size: {size // 1024 // 1024} MB")
                success = True
                break
            else:
                print(f"\nDownload seemed successful but file is small ({size} bytes). Trying next source.")
                os.remove(MODEL_PATH)

        except Exception as e:
            print(f"\nFailed to download from {url}: {e}")
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
    
    if not success:
        print("\nAll download attempts failed.")
        sys.exit(1)

if __name__ == "__main__":
    download_model()
