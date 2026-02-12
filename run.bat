@echo off
REM Windows batch script to run the Agentic Document Processor

echo.
echo ========================================
echo  Agentic Document Processor
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found
    echo Please create one with: python -m venv .venv
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found
    echo Copy .env.example to .env and configure your API keys
    pause
)

REM Run the Python script
python run.py

pause
