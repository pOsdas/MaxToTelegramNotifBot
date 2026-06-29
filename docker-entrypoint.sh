#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p   /app/runtime/data   /app/runtime/browser-profile   /app/runtime/screenshots   /app/runtime/logs

export DISPLAY="${DISPLAY:-:99}"
DISPLAY_NUMBER="${DISPLAY#:}"

rm -f "/tmp/.X${DISPLAY_NUMBER}-lock"
rm -f "/tmp/.X11-unix/X${DISPLAY_NUMBER}"

cleanup() {
  jobs -pr | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

Xvfb "$DISPLAY" -screen 0 1440x900x24 -ac +extension RANDR   > /app/runtime/logs/xvfb.log 2>&1 &

for _ in $(seq 1 50); do
  if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

fluxbox > /app/runtime/logs/fluxbox.log 2>&1 &

x11vnc   -display "$DISPLAY"   -forever   -shared   -localhost   -nopw   -rfbport 5900   -noxdamage   > /app/runtime/logs/x11vnc.log 2>&1 &

websockify   --web=/usr/share/novnc/   6080   localhost:5900   > /app/runtime/logs/novnc.log 2>&1 &

exec "$@"
