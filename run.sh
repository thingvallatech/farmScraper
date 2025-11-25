#!/bin/bash

# Farm Assist - Quick Start Script

set -e

echo "======================================"
echo "Farm Assist - FSA Data Collection"
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import playwright" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt

    echo "Installing Playwright browsers..."
    playwright install chromium

    echo "Installing Spacy model..."
    python -m spacy download en_core_web_sm
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if PostgreSQL is running
if ! docker-compose ps | grep -q "farm_scraper_db.*Up"; then
    echo "Starting PostgreSQL..."
    docker-compose up -d postgres

    echo "Waiting for database to initialize..."
    sleep 10
fi

echo ""
echo "Starting pipeline..."
echo "======================================"
echo ""

# Run the pipeline
python src/main.py

echo ""
echo "======================================"
echo "Pipeline complete!"
echo "======================================"
echo ""
echo "Results:"
echo "  - Report: data/extraction_report.txt"
echo "  - Logs: logs/"
echo "  - Database: PostgreSQL (use 'docker-compose --profile dev up' for pgAdmin)"
echo ""
