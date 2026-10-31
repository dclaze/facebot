#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
jdk="${JAVA_HOME:-$PWD/.local/toolchains/jdk-17.0.21+9/Contents/Home}"
mkdir -p .local/java-tests
"$jdk/bin/javac" -d .local/java-tests android/app/src/main/java/org/facebot/ConnectionPolicy.java tests/ConnectionPolicyTest.java android/app/src/main/java/org/facebot/PerformanceFaceCue.java tests/PerformanceFaceCueTest.java android/app/src/main/java/org/facebot/PlaybackProbe.java tests/PlaybackProbeTest.java android/app/src/main/java/org/facebot/KioskStatus.java tests/KioskStatusTest.java android/app/src/main/java/org/facebot/EchoControl.java tests/EchoControlTest.java android/app/src/main/java/org/facebot/QuietControlState.java tests/QuietControlStateTest.java
"$jdk/bin/java" -cp .local/java-tests org.facebot.ConnectionPolicyTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.PerformanceFaceCueTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.PlaybackProbeTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.KioskStatusTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.EchoControlTest
"$jdk/bin/java" -cp .local/java-tests org.facebot.QuietControlStateTest
