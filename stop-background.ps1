# Stop the background train reservation app started by run-background.ps1.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pidFile = "app.pid"

# 이 창은 stop-background.vbs가 숨기지 않고 그대로 띄워서 "처리 중" 표시처럼 보여주고
# 끝나면 스스로 닫히게 함 - 메시지가 바로 사라지지 않게 잠깐 붙잡아둠.
function Exit-Script($code) {
    Start-Sleep -Seconds 2
    exit $code
}

if (-not (Test-Path $pidFile)) {
    Write-Host "실행 중인 것으로 기록된 프로세스가 없습니다." -ForegroundColor Yellow
    Exit-Script 0
}

$targetPid = Get-Content $pidFile

$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "PID $targetPid 는 이미 종료된 상태입니다. 정리합니다." -ForegroundColor Yellow
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Exit-Script 0
}

Stop-Process -Id $targetPid -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {
    Write-Host "정상 종료가 안 돼서 강제 종료합니다." -ForegroundColor Yellow
    Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
Write-Host "✓ 중단 완료 (PID $targetPid)" -ForegroundColor Green
Exit-Script 0
