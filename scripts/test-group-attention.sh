#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
jdk="${JAVA_HOME:-$PWD/.local/toolchains/jdk-17.0.21+9/Contents/Home}"
mkdir -p .local/java-tests
"$jdk/bin/javac" -d .local/java-tests android/app/src/main/java/org/facebot/GroupAttention.java tests/GroupAttentionTest.java
"$jdk/bin/java" -cp .local/java-tests org.facebot.GroupAttentionTest
