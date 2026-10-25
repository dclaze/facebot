#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build/tests
xcrun swiftc -swift-version 6 -strict-concurrency=complete ios/SceneImageClient.swift tests/SceneImagePacketTests.swift -o build/tests/scene-images
build/tests/scene-images
