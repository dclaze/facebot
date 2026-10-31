#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:=$HOME/Library/Android/sdk}"
if [ -z "${JAVA_HOME:-}" ]; then
  JAVA_HOME="$(find -L "$PWD/.local/toolchains" -path '*/Contents/Home' -type d | head -n 1)"
fi
export JAVA_HOME ANDROID_HOME
GRADLE="${GRADLE:-$PWD/.local/toolchains/gradle-8.11.1/bin/gradle}"
exec "$GRADLE" -p android --no-daemon assembleDebug
