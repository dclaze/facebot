#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
SDK="$(xcrun --sdk iphonesimulator --show-sdk-path)"
APP="$PWD/build/ios-simulator/Facebot.app"
mkdir -p "$APP"
SDKROOT="$SDK" xcrun swiftc -swift-version 6 -strict-concurrency=complete -sdk "$SDK" -target arm64-apple-ios17.0-simulator -parse-as-library ios/*.swift -o "$APP/Facebot"
cp ios/Info.plist "$APP/Info.plist"
rm -f "$APP/local-config.json"
if [ -f ios/local-config.json ]; then cp ios/local-config.json "$APP/local-config.json"; fi
codesign --force --sign - "$APP"
printf '%s\n' "$APP"
