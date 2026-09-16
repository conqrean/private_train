# Install/update Python dependencies for the train reservation app (Windows).
# Mirrors what was done manually: pip install -r requirements-windows.txt against
# whichever python this machine actually uses (venv if present, else PATH's python).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$logFile = "install.log"

function Write-Log($message, $color = "White") {
    Write-Host $message -ForegroundColor $color
    Add-Content -Path $logFile -Value $message -Encoding utf8 -ErrorAction SilentlyContinue
}

# 이 창은 INSTALL.vbs가 숨기지 않고 그대로 띄워서 pip 설치 과정이 실시간으로 보이게 함.
# 성공하면 잠깐 보여주고 닫히지만, 실패하면 에러를 읽을 시간도 없이 훅 닫혀버리면
# 곤란하니 키 입력을 받을 때까지 창을 붙잡아둠.
function Exit-Script($code) {
    if ($code -eq 0) {
        Start-Sleep -Seconds 2
    } else {
        Write-Host ""
        Read-Host "아무 키나 누르고 Enter를 치면 창이 닫힙니다"
    }
    exit $code
}

Remove-Item $logFile -ErrorAction SilentlyContinue

$pythonCmd = $null
if (Test-Path ".\venv\Scripts\python.exe") {
    $pythonCmd = ".\venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
}

if (-not $pythonCmd) {
    Write-Log "python을 찾을 수 없습니다. https://www.python.org/downloads/ 에서 Python 3.12+ 를 먼저 설치해주세요 (설치 시 'Add to PATH' 체크)." "Red"
    Exit-Script 1
}

Write-Log "✓ 사용할 python: $pythonCmd" "Yellow"

# pip 출력에 특수문자가 섞여도 안 죽게 (main.py 이모지 출력과 같은 이유로 UTF-8 강제).
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# stderr 한 줄만 나와도 $ErrorActionPreference=Stop 때문에 죽는 걸 방지 (전에 겪은 문제와 동일).
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"

Write-Log "패키지 설치 중... (몇 분 걸릴 수 있습니다)" "Green"
$installOutput = & $pythonCmd -m pip install -r requirements-windows.txt 2>&1
$installExit = $LASTEXITCODE
$installOutput | ForEach-Object { Add-Content -Path $logFile -Value $_ -Encoding utf8 -ErrorAction SilentlyContinue }

$ErrorActionPreference = $prevEAP

if ($installExit -ne 0) {
    Write-Log "✗ 설치 실패 (종료 코드 $installExit). $logFile 를 확인해주세요." "Red"
    Exit-Script 1
}

Write-Log "✓ 설치 완료" "Green"
Exit-Script 0
