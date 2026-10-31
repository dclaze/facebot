#!/usr/bin/env python3
"""Prepare the public Apple Silicon Mac host; --check is read-only."""
import argparse
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('qwen2.5:1.5b', 'qwen3-vl:2b-instruct')


def find_tool(name):
    found = shutil.which(name)
    if found or name != 'ollama':
        return found
    for app in (Path('/Applications/Ollama.app'), Path.home() / 'Applications/Ollama.app'):
        candidate = app / 'Contents/Resources/ollama'
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def check(root, find=find_tool):
    token = root / '.local/pairing-token'
    valid_token = not token.exists() or (token.is_file() and len(token.read_text().strip()) >= 24)
    return {
        'apple_silicon_macos': platform.system() == 'Darwin' and platform.machine() == 'arm64',
        'uv_or_python312': bool(find('uv') or find('python3.12')),
        'ollama_installed': bool(find('ollama')),
        'requirements_lock': (root / 'requirements.lock').is_file(),
        'tokenizer_setup': (root / 'scripts/setup-tokenizer.py').is_file(),
        'prepared_speech_setup': (root / 'scripts/benchmark-kiosk.py').is_file(),
        'existing_token_valid_or_absent': valid_token,
        'environment_not_shared_symlink': not (root / '.venv').is_symlink(),
    }


def ensure_token(root):
    """Create once without a read/replace race; never display or rotate an old token."""
    local = root / '.local'
    local.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = local / 'pairing-token'
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if not path.is_file() or len(path.read_text().strip()) < 24:
            raise ValueError('Existing pairing token is invalid; repair it explicitly')
        return False
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(secrets.token_urlsafe(32) + '\n')
    return True


def run(command, root, env=None):
    subprocess.run(command, cwd=root, env=env, check=True)


def commands(root, skip_models=False, find=find_tool):
    python = str(root / '.venv/bin/python')
    uv, py312 = find('uv'), find('python3.12')
    if not uv and not py312:
        raise ValueError('Install uv or Python 3.12 yourself before setup')
    steps = []
    if not (root / '.venv').exists():
        steps.append([uv, 'venv', '--python', '3.12', str(root / '.venv')] if uv else
                     [py312, '-m', 'venv', str(root / '.venv')])
    steps.append([python, '-c', 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'])
    steps.append([uv, 'pip', 'sync', '--python', python, str(root / 'requirements.lock')] if uv else
                 [python, '-m', 'pip', 'install', '-r', str(root / 'requirements.lock')])
    steps.append([python, str(root / 'scripts/setup-tokenizer.py')])
    if not skip_models:
        ollama = find('ollama')
        if not ollama:
            raise ValueError('Install and start local Ollama before downloading the models')
        steps.extend([[ollama, 'pull', model] for model in MODELS])
        steps.append([python, str(root / 'scripts/setup-kiosk.py'), '--root', str(root), '--warm-models'])
    return steps


def warm_models(root):
    """Synthetic local setup only: no microphone, camera or cloud inference."""
    sys.path.insert(0, str(root))
    import numpy as np
    import mlx_whisper
    from huggingface_hub import snapshot_download
    from server.tts import SpeechEngine
    from server.profiles import load
    from server.settings import read
    profile = load('halloween')
    voice = profile['character_profile']['voice']
    rate = read()['speech_rate']
    snapshot_download('mlx-community/Kokoro-82M-bf16')
    snapshot_download('mlx-community/whisper-tiny.en-mlx')
    engine = SpeechEngine(voice=voice, speed=rate)
    try:
        if not engine.synthesize('Happy Halloween!'):
            raise RuntimeError('Speech prewarm produced no audio')
    finally:
        engine.executor.shutdown()
    mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32),
                           path_or_hf_repo='mlx-community/whisper-tiny.en-mlx')
    run([sys.executable, str(root / 'scripts/benchmark-kiosk.py'), '--prewarm',
         '--speech-rate', str(rate), '--voice', voice,
         '--output', str(root / '.local/setup/kiosk-prewarm.json')], root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true', help='Inspect prerequisites only; write and install nothing')
    parser.add_argument('--skip-models', action='store_true', help='Install Python dependencies/tokenizer only; not offline-ready')
    parser.add_argument('--warm-models', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if args.warm_models:
        if args.check:
            parser.error('--warm-models and --check cannot be combined')
        warm_models(root)
        return 0
    checks = check(root)
    if args.check:
        print(json.dumps({'mode': 'read_only', 'root': str(root), 'checks': checks,
                          'note': 'Prerequisites only; model readiness and device acceptance are not tested.'}, indent=2))
        return 0 if all(checks.values()) else 1
    required = {key: value for key, value in checks.items() if key != 'ollama_installed' or not args.skip_models}
    if not all(required.values()):
        print(json.dumps({'missing': [key for key, value in required.items() if not value]}, indent=2))
        return 1
    env = os.environ.copy()
    env.update(FACEBOT_PROFILE='halloween', FACEBOT_LLM='qwen2.5:1.5b', FACEBOT_TTS='kokoro',
               FACEBOT_KIOSK_MODE='1', FACEBOT_PREPARED_CACHE=str(root / '.local/prepared-audio'))
    if not args.skip_models:
        # Read-only daemon preflight before changing the environment. Never start
        # or upgrade an existing shared Ollama service on the user's behalf.
        run([find_tool('ollama'), 'list'], root, env)
    for command in commands(root, args.skip_models):
        run(command, root, env)
    created = ensure_token(root)
    print('Host setup finished. Pairing token created privately.' if created else
          'Host setup finished. Existing pairing token preserved.')
    if args.skip_models:
        print('Model preparation skipped; offline readiness has NOT been established.')
    print('No server, LaunchAgent or Android install was started. Continue with docs/PUBLIC_SETUP.md.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Setup did not complete. Check the failed local prerequisite or command; existing pairing data was not replaced.', file=sys.stderr)
        raise SystemExit(1)
