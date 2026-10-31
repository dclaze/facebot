#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
jdk="${JAVA_HOME:-$PWD/.local/toolchains/jdk-17.0.21+9/Contents/Home}"
mkdir -p .local/thermal-tests
"$jdk/bin/javac" -d .local/thermal-tests \
  android/app/src/main/java/org/facebot/ThermalCadence.java tests/ThermalCadenceTest.java \
  android/app/src/main/java/org/facebot/AnalysisFrameGate.java tests/AnalysisFrameGateTest.java
"$jdk/bin/java" -cp .local/thermal-tests org.facebot.ThermalCadenceTest
"$jdk/bin/java" -cp .local/thermal-tests org.facebot.AnalysisFrameGateTest
