#!/usr/bin/env python3
"""Build a credential-free signed alpha. Signing secrets never enter command text or logs."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local/android-release'
PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
PRIVATE.chmod(0o700)
JAVA = Path(os.environ.get('JAVA_HOME', ROOT / '.local/toolchains/jdk-17.0.21+9/Contents/Home'))
SDK = Path(os.environ.get('ANDROID_HOME', Path.home() / 'Library/Android/sdk'))
GRADLE = os.environ.get('GRADLE', str(ROOT / '.local/toolchains/gradle-8.11.1/bin/gradle'))
secret_file = PRIVATE / 'signing.json'
key_file = PRIVATE / 'facebot-release.jks'
if not secret_file.exists():
    if key_file.exists():
        raise SystemExit('Existing signing key has no password record; restore it before building.')
    with secret_file.open('x') as target:
        os.chmod(secret_file, 0o600)
        json.dump({'password': secrets.token_urlsafe(36)}, target)
password = json.loads(secret_file.read_text())['password']
env = dict(os.environ, JAVA_HOME=str(JAVA), ANDROID_HOME=str(SDK),
           FACEBOT_KEYSTORE=str(key_file), FACEBOT_KEYSTORE_PASSWORD=password)
if not key_file.exists():
    subprocess.run([str(JAVA / 'bin/keytool'), '-genkeypair', '-keystore', str(key_file),
                    '-storepass:env', 'FACEBOT_KEYSTORE_PASSWORD', '-keypass:env', 'FACEBOT_KEYSTORE_PASSWORD',
                    '-alias', 'facebot', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000',
                    '-dname', 'CN=Facebot Alpha, OU=Public Release, O=Facebot'], env=env, check=True)
    key_file.chmod(0o600)
subprocess.run([GRADLE, '-p', str(ROOT / 'android'), '--no-daemon', 'assembleRelease'], env=env, check=True)
apk = ROOT / 'android/app/build/outputs/apk/release/app-release.apk'
with zipfile.ZipFile(apk) as archive:
    forbidden = [name for name in archive.namelist() if any(value in name.lower() for value in
                 ('local-config', '.keystore', '.jks', 'signing.json', 'robin-integration', 'ghost-comedy'))]
    if forbidden:
        raise SystemExit('Private asset inclusion detected; do not publish.')
build_tools = sorted((SDK / 'build-tools').iterdir())[-1]
subprocess.run([str(build_tools / 'apksigner'), 'verify', '--verbose', str(apk)], env=env, check=True)
manifest = subprocess.check_output([str(build_tools / 'aapt'), 'dump', 'badging', str(apk)], text=True)
if 'application-debuggable' in manifest:
    raise SystemExit('Release unexpectedly debuggable; do not publish.')
receipt = {'apk': str(apk), 'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
           'bytes': apk.stat().st_size, 'private_assets_found': False, 'debuggable': False,
           'signature_verified': True, 'signing': 'dedicated private alpha release key'}
(PRIVATE / 'public-apk-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
