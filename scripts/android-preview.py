#!/usr/bin/env python3
"""Install/start or stop the private USB-paired Android development preview.

Requires exactly one owner-authorized device. Does not grant permissions,
enroll devices or change kiosk configuration. Never prints device identifiers.
"""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    adb = Path.home() / 'Library/Android/sdk/platform-tools/adb'
    inventory = subprocess.check_output([str(adb), 'devices'], text=True)
    devices = [line.split()[0] for line in inventory.splitlines()[1:]
               if len(line.split()) >= 2 and line.split()[1] == 'device']
    if len(devices) != 1:
        print('Exactly one USB-debug-authorized Android device is required; no device changed.')
        return 2
    command = [str(adb), '-s', devices[0]]
    def run(*arguments):
        result = subprocess.run(command + list(arguments), capture_output=True)
        if result.returncode:
            raise RuntimeError('ADB operation failed; inspect locally without publishing device details')
    if args.action == 'stop':
        run('shell', 'am', 'force-stop', 'org.facebot')
        print('Android app force-stopped. Physical silence still requires observation.')
        return 0
    config = root / 'android/app/src/debug/assets/local-config.json'
    apk = root / 'android/app/build/outputs/apk/debug/app-debug.apk'
    if not config.exists() or not apk.exists() or apk.stat().st_mtime < config.stat().st_mtime:
        raise RuntimeError('Build the private paired APK before starting the preview')
    run('reverse', 'tcp:8765', 'tcp:8765')
    run('install', '-r', str(apk))
    run('shell', 'am', 'start', '-n', 'org.facebot/.FaceActivity')
    print('Preview launched. Native microphone/server/playback checks are still required before readiness.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
