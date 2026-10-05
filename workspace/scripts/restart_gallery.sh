#!/usr/bin/env bash
# Перезапуск галереи после правок gallery_server.py.
# Usage: workspace/scripts/restart_gallery.sh [port=9000]
# Останавливает старый процесс (по PID-файлу, затем по порту), проверяет синтаксис, стартует заново в фоне,
# ждёт ответа и печатает адрес. Лог: workspace/gallery.log, PID: workspace/.gallery.pid (оба в .gitignore).
set -euo pipefail

PORT="${1:-9000}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(dirname "$DIR")"
SERVER="$DIR/gallery_server.py"
PIDFILE="$WS/.gallery.pid"
LOG="$WS/gallery.log"

python3 -m py_compile "$SERVER" || { echo "ОШИБКА: синтаксис gallery_server.py, старый процесс не тронут" >&2; exit 1; }

stop_pid() {  # TERM, до 5 с ждём, затем KILL
  local pid="$1" i
  kill -0 "$pid" 2>/dev/null || return 0
  kill "$pid" 2>/dev/null || true
  for i in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || return 0; sleep 0.5; done
  kill -9 "$pid" 2>/dev/null || true
}

if [ -f "$PIDFILE" ]; then stop_pid "$(cat "$PIDFILE")"; rm -f "$PIDFILE"; fi
# запущенная вручную копия: берём PID того, кто слушает порт, и убеждаемся, что это наш скрипт
old="$(ss -ltnpH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true)"
if [ -n "$old" ]; then
  if tr '\0' ' ' < "/proc/$old/cmdline" | grep -q 'gallery_server.py'; then stop_pid "$old"
  else echo "ОШИБКА: порт $PORT занят другим процессом (pid $old)" >&2; exit 1; fi
fi

cd "$WS/.."
setsid nohup python3 -u -B "$SERVER" --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"

for i in $(seq 1 20); do
  if curl -fs -o /dev/null "http://127.0.0.1:$PORT/"; then
    ip="$(curl -s -m 4 https://api.ipify.org || hostname -I | awk '{print $1}')"
    echo "OK: галерея запущена (pid $(cat "$PIDFILE")), адрес: http://$ip:$PORT/"
    exit 0
  fi
  sleep 0.5
done
echo "ОШИБКА: сервер не ответил за 10 с, смотрите $LOG" >&2
tail -5 "$LOG" >&2
exit 1
