#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p build/tests
xcrun swiftc -swift-version 6 -strict-concurrency=complete ios/AttentionGeometry.swift tests/AttentionGeometryTests.swift -o build/tests/attention
build/tests/attention
