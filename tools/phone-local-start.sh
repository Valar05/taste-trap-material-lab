#!/data/data/com.termux/files/usr/bin/bash
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
STATE="$HOME/.local/state/taste-trap-material-lab"
PORT="${TTML_PORT:-4173}"
URL="http://127.0.0.1:${PORT}/"
SESSION="taste-trap-material-lab"
mkdir -p "$STATE"

if command -v python >/dev/null 2>&1; then
  PYTHON=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  echo "BLOCKED: Python is not installed in Termux." >&2
  exit 2
fi

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
  fi
  tmux new-session -d -s "$SESSION" "cd '$ROOT' && exec '$PYTHON' -m http.server '$PORT' --bind 127.0.0.1"
  printf '%s\n' "tmux:$SESSION" > "$STATE/owner"
else
  if [ -f "$STATE/server.pid" ]; then
    OLD_PID="$(sed -n '1p' "$STATE/server.pid" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && [ -r "/proc/$OLD_PID/cmdline" ] && tr '\000' ' ' < "/proc/$OLD_PID/cmdline" | grep -F "http.server $PORT" >/dev/null 2>&1; then
      kill "$OLD_PID"
    fi
  fi
  nohup "$PYTHON" -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT" >"$STATE/server.log" 2>&1 &
  printf '%s\n' "$!" > "$STATE/server.pid"
  printf '%s\n' "pid:$!" > "$STATE/owner"
fi

"$PYTHON" - "$URL" <<'PY'
import sys, time, urllib.request
base = sys.argv[1]
required = (
    "index.html",
    "viewer.js",
    "assets/FPSPlayer.glb",
    "assets/fps-arms-basecolor.png",
    "assets/fps-arms-normal.png",
    "assets/fps-arms-roughness.png",
    "assets/fps-arms-metallic.png",
)
last = None
for _ in range(20):
    try:
        for path in required:
            with urllib.request.urlopen(base + path, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError(f"{path}: HTTP {response.status}")
                response.read(16)
        print("PHONE_LOCAL_WEBGL_READY " + base)
        break
    except Exception as exc:
        last = exc
        time.sleep(0.25)
else:
    raise SystemExit("BLOCKED: local server probe failed: " + str(last))
PY

printf '%s\n' "$URL" > "$STATE/url"
echo "OPEN $URL"
