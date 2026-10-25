#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build/tests
xcrun swiftc -swift-version 6 -strict-concurrency=complete ios/VisemeTimeline.swift tests/VisemeTimelineTests.swift -o build/tests/visemes
build/tests/visemes
