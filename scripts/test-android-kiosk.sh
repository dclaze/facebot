#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
jdk="${JAVA_HOME:-$PWD/.local/toolchains/jdk-17.0.21+9/Contents/Home}"
mkdir -p .local/java-tests
"$jdk/bin/javac" -d .local/java-tests android/app/src/main/java/org/facebot/ConnectionPolicy.java tests/ConnectionPolicyTest.java android/app/src/main/java/org/facebot/PerformanceFaceCue.java tests/PerformanceFaceCueTest.java android/app/src/main/java/org/facebot/PlaybackProbe.java tests/PlaybackProbeTest.java
"$jdk/bin/java" -cp .local/java-tests org.facebot.ConnectionPolicyTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.PerformanceFaceCueTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.PlaybackProbeTest
