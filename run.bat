@echo off
REM Farm Assist - Quick Start Script (Windows)

echo ======================================
echo Farm Assist - FSA Data Collection
echo ======================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import playwright" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt

    echo Installing Playwright browsers...
    playwright install chromium

    echo Installing Spacy model...
    python -m spacy download en_core_web_sm
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker and try again.
    exit /b 1
)

REM Check if PostgreSQL is running
docker-compose ps | findstr "farm_scraper_db" | findstr "Up" >nul
if errorlevel 1 (
    echo Starting PostgreSQL...
    docker-compose up -d postgres

    echo Waiting for database to initialize...
    timeout /t 10 /nobreak >nul
)

echo.
echo Starting pipeline...
echo ======================================
echo.

REM Run the pipeline
python src\main.py

echo.
echo ======================================
echo Pipeline complete!
echo ======================================
echo.
echo Results:
echo   - Report: data\extraction_report.txt
echo   - Logs: logs\
echo   - Database: PostgreSQL (use 'docker-compose --profile dev up' for pgAdmin)
echo.

pause
