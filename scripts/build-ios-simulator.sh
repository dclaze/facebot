#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
SDK="$(xcrun --sdk iphonesimulator --show-sdk-path)"
APP="$PWD/build/ios-simulator/Facebot.app"
mkdir -p "$APP"
xcrun swiftc -sdk "$SDK" -target arm64-apple-ios17.0-simulator -parse-as-library ios/Facebot.swift -o "$APP/Facebot"
cp ios/Info.plist "$APP/Info.plist"
codesign --force --sign - "$APP"
printf '%s\n' "$APP"
