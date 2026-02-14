# Train Reservation App - Virtual Environment Activation Script
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Train Reservation App - Virtual Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host "Python version:" -ForegroundColor Yellow
python --version
Write-Host ""
Write-Host "IMPORTANT: Use " -NoNewline -ForegroundColor Red
Write-Host "python" -NoNewline -ForegroundColor Yellow
Write-Host " (not python3) in virtual environment!" -ForegroundColor Red
Write-Host ""
Write-Host "To run the application: " -NoNewline -ForegroundColor White
Write-Host "python main.py" -ForegroundColor Green
Write-Host "To deactivate         : " -NoNewline -ForegroundColor White
Write-Host "deactivate" -ForegroundColor Green
Write-Host ""
