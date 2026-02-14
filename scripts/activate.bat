@echo off
echo ========================================
echo Train Reservation App - Virtual Environment
echo ========================================
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.
echo Virtual environment activated!
echo Python version:
python --version
echo.
echo IMPORTANT: Use 'python' (not python3) in virtual environment!
echo.
echo To run the application: python main.py
echo To deactivate         : deactivate
echo.
