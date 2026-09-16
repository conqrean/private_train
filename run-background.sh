#!/usr/bin/env bash
# Train Reservation App - 백그라운드 실행 스크립트
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_DIR="$SCRIPT_DIR/.run"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$RUN_DIR/app.pid"
LOCK_FILE="$RUN_DIR/app.lock"
MAIN_PY="$SCRIPT_DIR/main.py"
PORT="${PORT:-5050}"
MAX_PORT_TRIES=20
KEEP_LOGS=10

FORCE_RESTART=0
STRICT_PORT=0
for arg in "$@"; do
    case "$arg" in
        -f|--force|--restart) FORCE_RESTART=1 ;;
        --strict-port) STRICT_PORT=1 ;;
        -h|--help)
            cat <<'USAGE'
Usage: ./run-background.sh [옵션]

옵션:
  -f, --force, --restart   이미 실행 중이면 묻지 않고 재시작
  --strict-port            포트가 사용 중이면 다른 포트로 바꾸지 않고 중단
  -h, --help               도움말

환경변수:
  PORT          시작 포트 (기본: 5050, 사용 중이면 비어있는 포트를 자동 탐색)
  FLASK_DEBUG   디버그 모드 (기본: false)
USAGE
            exit 0 ;;
        *) echo "알 수 없는 옵션: $arg (--help 참고)" >&2; exit 1 ;;
    esac
done

mkdir -p "$RUN_DIR" "$LOG_DIR"

# ── 동시 실행 방지 락 ────────────────────────────────────────────────
# run/stop 스크립트가 동시에 돌아 프로세스가 중복 기동되는 것을 막는다.
LOCK_DIR_FALLBACK="$RUN_DIR/app.lock.d"
release_fallback_lock() { rmdir "$LOCK_DIR_FALLBACK" 2>/dev/null; }

if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        echo "⚠️  다른 run/stop 스크립트가 실행 중입니다. 잠시 후 다시 시도하세요." >&2
        exit 1
    fi
else
    if ! mkdir "$LOCK_DIR_FALLBACK" 2>/dev/null; then
        echo "⚠️  다른 run/stop 스크립트가 실행 중입니다. 잠시 후 다시 시도하세요." >&2
        echo "   (오래된 락이면 삭제: rm -rf '$LOCK_DIR_FALLBACK')" >&2
        exit 1
    fi
    trap release_fallback_lock EXIT
fi

# ── 프로세스 식별 ────────────────────────────────────────────────────
# 이 프로젝트의 프로세스만 대상으로 한다.
#  1) 실행 인자에 이 프로젝트의 절대경로 main.py 가 있거나
#  2) main.py 를 실행 중이면서 작업 디렉터리가 이 프로젝트인 경우
proc_cwd() {
    if [[ -r "/proc/$1/cwd" ]]; then
        readlink "/proc/$1/cwd" 2>/dev/null
    elif command -v lsof >/dev/null 2>&1; then
        lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
    fi
}

# 자기 자신 / 조상 프로세스는 절대 대상으로 삼지 않는다.
is_self_or_ancestor() {
    local target="$1" p="$$"
    while [[ -n "$p" && "$p" != "0" && "$p" != "1" ]]; do
        [[ "$p" == "$target" ]] && return 0
        p="$(ps -p "$p" -o ppid= 2>/dev/null | tr -d ' ')"
    done
    return 1
}

# 실제로 "이 프로젝트의 main.py 를 실행 중인 python 프로세스" 인지 확인한다.
# 명령줄에 main.py 라는 글자가 들어있을 뿐인 셸/에디터 등은 걸러진다.
is_our_process() {
    local pid="$1" args exe tok script=""
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    is_self_or_ancestor "$pid" && return 1
    args="$(ps -p "$pid" -o args= 2>/dev/null)" || return 1
    [[ -n "$args" ]] || return 1

    set -- $args
    exe="${1##*/}"
    [[ "$exe" == python* ]] || return 1
    shift

    for tok in "$@"; do
        [[ "$tok" == -* ]] && continue
        script="$tok"
        break
    done

    case "$script" in
        "$MAIN_PY") return 0 ;;
        main.py|./main.py) [[ "$(proc_cwd "$pid")" == "$SCRIPT_DIR" ]] ;;
        *) return 1 ;;
    esac
}

running_pid() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid="$(cat "$PID_FILE" 2>/dev/null)"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && is_our_process "$pid"; then
            echo "$pid"
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    local pid
    while read -r pid; do
        [[ -z "$pid" ]] && continue
        if is_our_process "$pid"; then
            echo "$pid"
            return 0
        fi
    done < <(pgrep -f 'main\.py' 2>/dev/null)
    return 1
}

stop_app() {
    local pid="$1"
    echo "⏹️  기존 프로세스 종료 중 (PID: $pid)..."
    kill -TERM "$pid" 2>/dev/null
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  정상 종료되지 않아 강제 종료합니다."
        kill -KILL "$pid" 2>/dev/null
        sleep 1
    fi
    if kill -0 "$pid" 2>/dev/null; then
        echo "❌ PID $pid 를 종료하지 못했습니다 (권한 부족일 수 있음)." >&2
        exit 1
    fi
    rm -f "$PID_FILE"
    echo "✅ 종료 완료"
}

if PID="$(running_pid)"; then
    echo "⚠️  앱이 이미 실행 중입니다 (PID: $PID)"
    if [[ "$FORCE_RESTART" -eq 1 ]]; then
        stop_app "$PID"
    elif [[ -t 0 ]]; then
        read -r -p "재시작할까요? [y/N] " answer
        case "$answer" in
            [yY]|[yY][eE][sS]) stop_app "$PID" ;;
            *) echo "취소했습니다. 기존 프로세스를 그대로 둡니다."; exit 0 ;;
        esac
    else
        echo "대화형 터미널이 아니므로 종료합니다. 재시작하려면 --force 를 사용하세요."
        exit 1
    fi
fi

# ── Python 인터프리터 선택 (venv 우선) ───────────────────────────────
if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
    echo "ℹ️  가상환경이 없어 시스템 python3 를 사용합니다."
else
    echo "❌ python 을 찾을 수 없습니다." >&2
    exit 1
fi

# ── 포트 충돌 회피 ───────────────────────────────────────────────────
port_free() {
    "$PYTHON" - "$1" <<'PY'
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

REQUESTED_PORT="$PORT"
if ! port_free "$PORT"; then
    if [[ "$STRICT_PORT" -eq 1 ]]; then
        echo "❌ 포트 $PORT 가 이미 사용 중입니다. 다른 포트를 지정하세요: PORT=5051 ./run-background.sh" >&2
        exit 1
    fi
    echo "⚠️  포트 $PORT 가 이미 사용 중입니다. 비어있는 포트를 찾는 중..."
    found=0
    for ((i = 1; i < MAX_PORT_TRIES; i++)); do
        candidate=$((REQUESTED_PORT + i))
        if port_free "$candidate"; then
            PORT="$candidate"
            found=1
            break
        fi
    done
    if [[ "$found" -eq 0 ]]; then
        echo "❌ $REQUESTED_PORT ~ $((REQUESTED_PORT + MAX_PORT_TRIES - 1)) 사이에 비어있는 포트가 없습니다." >&2
        exit 1
    fi
    echo "ℹ️  포트 $PORT 로 대신 실행합니다."
fi

# ── 캐시 정리 (최신 코드 보장) ───────────────────────────────────────
find app korail2 SRT -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
find app korail2 SRT -name '*.py[co]' -type f -delete 2>/dev/null

# ── 로그 파일 (실행마다 분리, 최근 N개만 보관) ───────────────────────
LOG_FILE="$LOG_DIR/app-$(date +%Y%m%d-%H%M%S).log"
ls -1t "$LOG_DIR"/app-*.log 2>/dev/null | tail -n "+$((KEEP_LOGS + 1))" | while read -r old; do
    rm -f "$LOG_DIR/$(basename "$old")"
done
: > "$LOG_FILE"
ln -sfn "$LOG_FILE" "$LOG_DIR/latest.log"

echo "🚄 백그라운드로 시작합니다 (포트: $PORT)"
PORT="$PORT" FLASK_DEBUG="${FLASK_DEBUG:-false}" \
    nohup "$PYTHON" "$MAIN_PY" >> "$LOG_FILE" 2>&1 9>&- &
APP_PID=$!
echo "$APP_PID" > "$PID_FILE"

# ── 기동 확인 ────────────────────────────────────────────────────────
sleep 2
if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "❌ 실행에 실패했습니다. 로그를 확인하세요: $LOG_FILE" >&2
    tail -n 20 "$LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
fi

echo "✅ 실행 중 (PID: $APP_PID)"
echo "   URL : http://localhost:$PORT"
echo "   로그: $LOG_FILE"
echo "         tail -f $LOG_DIR/latest.log"
echo "   중지: ./stop-background.sh"
