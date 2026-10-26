#!/usr/bin/env python3
"""Download pinned open Qwen weights once; runtime inference stays local."""
from huggingface_hub import snapshot_download

MODEL = 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit'
REVISION = 'f35faf19b0cc2160865af64ecf0f22f83d335135'

if __name__ == '__main__':
    snapshot_download(MODEL, revision=REVISION)
    print('Expressive Qwen voice installed. No live backend was changed.')
