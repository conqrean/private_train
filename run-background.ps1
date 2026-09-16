# Start the train reservation app in the background (Windows).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pidFile = "app.pid"
$logFile = "app.log"

# Write-Host is invisible when this script is launched hidden (e.g. from
# start-background.vbs), so every message that matters also goes into $logFile -
# otherwise a pre-flight failure (already running, no python found, ...) leaves
# no trace anywhere and "확인해주세요 app.log" in the vbs popup would be a lie.
function Write-Log($message, $color = "White") {
    Write-Host $message -ForegroundColor $color
    # 실패 로그 남기는 용도라 여기서 또 에러나면 안 되니 조용히 넘어감 (예: 파일이
    # Start-Process 리다이렉션에 아직 물려있는 경우).
    Add-Content -Path $logFile -Value $message -Encoding utf8 -ErrorAction SilentlyContinue
}

# 이 창은 start-background.vbs가 숨기지 않고 그대로 띄워서 "로딩 중" 표시처럼 보여주고
# 끝나면 스스로 닫히게 함. 성공하면 잠깐 보여주고 바로 닫히지만, 실패하면 에러를 읽을
# 시간도 없이 훅 닫혀버리면 곤란하니 키 입력을 받을 때까지 창을 붙잡아둠.
function Exit-Script($code) {
    if ($code -eq 0) {
        Start-Sleep -Seconds 2
    } else {
        Write-Host ""
        Read-Host "아무 키나 누르고 Enter를 치면 창이 닫힙니다"
    }
    exit $code
}

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Log "이미 실행 중입니다 (PID $existingPid). 먼저 .\stop-background.ps1 로 중단하세요." "Yellow"
        Exit-Script 1
    }
}

# venv가 있으면 그걸 쓰고, 없으면 PATH의 시스템 python을 그대로 씀 (지금 이 PC처럼
# venv 없이 python main.py로 직접 돌리는 경우도 지원).
$pythonCmd = $null
if (Test-Path ".\venv\Scripts\python.exe") {
    $pythonCmd = ".\venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if (-not $pythonCmd) {
    Write-Log "python을 찾을 수 없습니다. venv를 만들거나(python -m venv venv) python을 PATH에 설치해주세요." "Red"
    Exit-Script 1
}

# $ErrorActionPreference = "Stop" 때문에 파이썬이 stderr에 한 줄만 써도 그 자리에서
# 스크립트가 죽어버려서(전체 에러 내용도 못 보고) 아래에서 실제로 체크하기 전에 멈추는
# 문제가 있었음 - 이 호출 동안만 잠깐 꺼서 끝까지 실행되고 종료코드로 판단하게 함.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$flaskCheck = & $pythonCmd -c "import flask" 2>&1
$ErrorActionPreference = $prevEAP

if ($LASTEXITCODE -ne 0) {
    Write-Log "Flask가 설치돼 있지 않습니다 ($pythonCmd). 먼저 설치해주세요: $pythonCmd -m pip install -r requirements-windows.txt" "Red"
    Write-Log "  (실제 오류: $flaskCheck)" "Red"
    Exit-Script 1
}

Write-Log "✓ 파이썬 캐시 정리 중..." "Yellow"
Get-ChildItem -Recurse -Path app,korail2,SRT -Include *.pyc,__pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 백그라운드 실행에서는 Flask 디버그 리로더를 꺼야 함 - 켜져 있으면 감시 프로세스가
# 하나 더 떠서(실제 서버는 자식 프로세스), 여기서 기록한 PID를 죽여도 자식이 남거나
# 텔레그램 getUpdates 폴링이 두 프로세스에서 겹쳐 중복 응답이 나는 원인이 될 수 있음.
$env:FLASK_DEBUG = "false"

# main.py가 이모지를 print하는데, 콘솔이 아니라 파일로 출력을 리다이렉트하면 파이썬이
# 시스템 코드페이지(한국어 Windows는 cp949)로 인코딩하려다 죽어버림 - UTF-8로 강제.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Log "🚄 백그라운드로 시작 중... ($pythonCmd)" "Green"

# Start-Process -RedirectStandardOutput는 대상 파일이 이미 있으면 문제가 될 수 있어서
# (버전에 따라 에러) 위에서 Write-Log로 이미 app.log에 몇 줄 써놨을 수 있는 걸 여기서 지움.
Remove-Item $logFile -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $pythonCmd -ArgumentList "main.py" `
    -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" `
    -WindowStyle Hidden -PassThru

$proc.Id | Out-File -FilePath $pidFile -Encoding ascii

# 포트 충돌 등으로 죽는 경우 곧바로 안 죽고 잠깐 뒤에 죽을 수 있어서, 1초 한 번이 아니라
# 3초 동안 살아있는지 반복 확인함 (너무 일찍 확인하면 죽는 중인데도 "시작됨"으로 오판함).
$alive = $false
for ($i = 0; $i -lt 6; $i++) {
    Start-Sleep -Milliseconds 500
    $alive = [bool](Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)
    if (-not $alive) { break }
}

if ($alive) {
    Write-Log "✓ 시작됨 (PID $($proc.Id))" "Green"
    Write-Log "  로그 보기: Get-Content $logFile -Wait" "Cyan"
    Write-Log "  중단하기: .\stop-background.ps1" "Cyan"
    Exit-Script 0
} else {
    $errTail = ""
    if (Test-Path "$logFile.err") {
        $errTail = (Get-Content "$logFile.err" -Tail 5) -join "`n"
    }
    Write-Log "✗ 시작 실패. 포트가 이미 사용 중이거나 다른 오류입니다." "Red"
    if ($errTail) { Write-Log $errTail "Red" }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Exit-Script 1
}
