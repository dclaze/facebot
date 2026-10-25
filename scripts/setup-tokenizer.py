#!/usr/bin/env python3
"""Install only the pinned official text tokenizer, not model weights."""
from pathlib import Path
from huggingface_hub import snapshot_download

snapshot_download('Qwen/Qwen2.5-1.5B-Instruct',
    revision='989aa7980e4cf806f80c7fef2b1adb7bc71aa306',
    allow_patterns=['tokenizer.json','tokenizer_config.json','special_tokens_map.json'],
    local_dir=Path(__file__).resolve().parents[1]/'.local/tokenizers/qwen2.5-1.5b')
