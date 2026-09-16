#!/usr/bin/env bash
# Train Reservation App - 백그라운드 종료 스크립트
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_DIR="$SCRIPT_DIR/.run"
PID_FILE="$RUN_DIR/app.pid"
LOCK_FILE="$RUN_DIR/app.lock"
MAIN_PY="$SCRIPT_DIR/main.py"

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat <<'USAGE'
Usage: ./stop-background.sh

백그라운드로 실행 중인 이 프로젝트의 앱을 종료합니다.
USAGE
            exit 0 ;;
        *) echo "알 수 없는 옵션: $arg (--help 참고)" >&2; exit 1 ;;
    esac
done

mkdir -p "$RUN_DIR"

# ── 동시 실행 방지 락 (run-background.sh 와 공유) ────────────────────
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

# ── 프로세스 식별 (run-background.sh 와 동일 기준) ───────────────────
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

PIDS=()
if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && is_our_process "$pid"; then
        PIDS+=("$pid")
    fi
fi

# PID 파일에 없는 잔여 프로세스도 정리 (이 프로젝트 것만)
while read -r p; do
    [[ -z "$p" ]] && continue
    [[ " ${PIDS[*]-} " == *" $p "* ]] && continue
    is_our_process "$p" || continue
    PIDS+=("$p")
done < <(pgrep -f 'main\.py' 2>/dev/null)

if [[ ${#PIDS[@]} -eq 0 ]]; then
    echo "ℹ️  실행 중인 프로세스가 없습니다."
    rm -f "$PID_FILE"
    exit 0
fi

for pid in "${PIDS[@]}"; do
    echo "⏹️  종료 중 (PID: $pid)..."
    kill -TERM "$pid" 2>/dev/null
done

for _ in $(seq 1 20); do
    alive=0
    for pid in "${PIDS[@]}"; do
        kill -0 "$pid" 2>/dev/null && alive=1
    done
    [[ "$alive" -eq 0 ]] && break
    sleep 0.5
done

for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  강제 종료합니다 (PID: $pid)"
        kill -KILL "$pid" 2>/dev/null
    fi
done
sleep 1

FAILED=()
for pid in "${PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null && FAILED+=("$pid")
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "❌ 종료하지 못한 프로세스: ${FAILED[*]} (권한 부족일 수 있음)" >&2
    exit 1
fi

rm -f "$PID_FILE"
echo "✅ 종료 완료"
