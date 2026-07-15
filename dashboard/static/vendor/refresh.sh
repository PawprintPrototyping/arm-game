#!/usr/bin/env bash
# Re-fetch vendored frontend libraries. Bump the versions here, then run:
#     ./dashboard/static/vendor/refresh.sh
# Remember to update the <script> tags in dashboard/static/index.html and
# the version table in README.md after changing anything.
set -euo pipefail

ALPINE_VERSION="3.14.1"
MQTT_VERSION="5.10.1"

here="$(cd "$(dirname "$0")" && pwd)"

fetch() {
  local url="$1"
  local out="$2"
  echo "→ $out"
  curl -fsSL --retry 3 -o "$out" "$url"
}

fetch \
  "https://cdn.jsdelivr.net/npm/alpinejs@${ALPINE_VERSION}/dist/cdn.min.js" \
  "${here}/alpine-${ALPINE_VERSION}.min.js"

fetch \
  "https://cdn.jsdelivr.net/npm/mqtt@${MQTT_VERSION}/dist/mqtt.min.js" \
  "${here}/mqtt-${MQTT_VERSION}.min.js"

echo "done. Remember to update index.html script tags + README.md table."
