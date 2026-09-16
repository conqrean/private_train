# Uninstall/clean up the train reservation app's generated files (Windows).
#
# 이 프로젝트는 venv 없이 시스템 python(전역 site-packages)에 패키지를 설치해서 쓰고
# 있어서, 여기서 pip uninstall로 flask/requests 등을 지우면 이 컴퓨터의 다른 파이썬
# 프로젝트가 같은 패키지를 쓰고 있을 경우 그것까지 같이 망가질 수 있음. 그래서 패키지
# 삭제는 하지 않고, 이 프로젝트가 만든 파일(실행 중인 프로세스, 캐시, 로그)만 정리함.
# venv 폴더가 있는 경우엔 그건 이 프로젝트 전용이라 안전하게 같이 지움.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$logFile = "uninstall.log"

function Write-Log($message, $color = "White") {
    Write-Host $message -ForegroundColor $color
    Add-Content -Path $logFile -Value $message -Encoding utf8 -ErrorAction SilentlyContinue
}

# 이 창은 UNINSTALL.vbs가 숨기지 않고 그대로 띄워서 "정리 중" 표시처럼 보여주고
# 끝나면 스스로 닫히게 함 - 메시지가 바로 사라지지 않게 잠깐 붙잡아둠.
function Exit-Script($code) {
    Start-Sleep -Seconds 2
    exit $code
}

Remove-Item $logFile -ErrorAction SilentlyContinue

# 1) 실행 중이면 먼저 중단
$pidFile = "app.pid"
if (Test-Path $pidFile) {
    $targetPid = Get-Content $pidFile
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Log "실행 중인 앱을 중단합니다 (PID $targetPid)..." "Yellow"
        Stop-Process -Id $targetPid -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

# 2) 생성됐던 파일 정리 (로그, 캐시, venv - venv는 이 프로젝트 전용이라 안전하게 삭제)
Write-Log "생성된 파일 정리 중..." "Yellow"
Remove-Item "app.log" -ErrorAction SilentlyContinue
Remove-Item "app.log.err" -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Path app,korail2,SRT -Include *.pyc,__pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path ".\venv") {
    Remove-Item ".\venv" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "  venv 폴더 삭제함" "Yellow"
}

Write-Log "✓ 정리 완료" "Green"
Write-Log "  (pip로 설치된 flask/requests 등은 다른 프로젝트와 공유하는 전역 환경이라 그대로 뒀습니다)" "Cyan"
Exit-Script 0
