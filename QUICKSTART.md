# Quick Start Guide

Get the Farm Assist scraper running in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- Docker Desktop installed and running
- 4GB+ RAM available

## Steps

### 1. Quick Run (Easiest)

```bash
# macOS/Linux
./run.sh

# Windows
run.bat
```

This script will:
- Create virtual environment
- Install all dependencies
- Start PostgreSQL
- Run the complete pipeline

### 2. Manual Setup

If you prefer to set up manually:

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install Python packages
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install chromium

# 4. Install Spacy model
python -m spacy download en_core_web_sm

# 5. Start PostgreSQL
docker-compose up -d postgres

# 6. Wait for database initialization (10 seconds)
sleep 10

# 7. Run the pipeline
python src/main.py
```

## What Happens Next?

The pipeline will:

1. **Tier 1 (5-10 min)**: Fetch data from NASS API and EWG database
2. **Tier 2 (30-60 min)**: Crawl FSA website and extract program data
3. **Tier 3 (20-40 min)**: Download and process PDF documents
4. **Analysis (1-2 min)**: Generate completeness report

**Total time**: ~1-2 hours

## Checking Progress

```bash
# Watch logs in real-time
tail -f logs/farm_scraper_$(date +%Y%m%d).log

# Check database
docker exec -it farm_scraper_db psql -U farm_user -d farm_scraper -c "SELECT COUNT(*) FROM programs;"
```

## Results

When complete, you'll find:

- **Report**: `data/extraction_report.txt` - Comprehensive analysis
- **Logs**: `logs/` - Detailed execution logs
- **Database**: PostgreSQL with all structured data
- **PDFs**: `data/pdfs/` - Downloaded documents

## View Results

### Quick Summary

```bash
cat data/extraction_report.txt
```

### Database (pgAdmin)

```bash
# Start pgAdmin
docker-compose --profile dev up -d

# Access at http://localhost:5050
# Email: admin@farmassist.local
# Password: admin
```

### Jupyter Analysis

```bash
jupyter notebook notebooks/analysis.ipynb
```

## Troubleshooting

### "Docker is not running"
Start Docker Desktop and wait for it to fully initialize.

### "Playwright browsers not found"
```bash
playwright install chromium
```

### "Database connection failed"
```bash
# Restart PostgreSQL
docker-compose restart postgres
```

### Memory issues
If the scraper crashes:
1. Close other applications
2. Reduce concurrent requests in `.env`:
   ```
   MAX_CONCURRENT_REQUESTS=1
   ```

## Customization

Edit `.env` to adjust:

```bash
# Focus on specific state
TARGET_STATE=ND

# Faster scraping (less polite)
SCRAPE_DELAY_SECONDS=1.0

# Only run certain tiers
ENABLE_TIER1=true
ENABLE_TIER2=true
ENABLE_TIER3=false  # Skip PDFs
```

## Stop Everything

```bash
# Stop pipeline: Ctrl+C

# Stop PostgreSQL
docker-compose down
```

## Next Steps

1. Review the extraction report
2. Query the database for specific programs
3. Analyze data in Jupyter notebook
4. Export results to CSV
5. Determine if data quality meets your needs

## Support

See README.md for full documentation and deployment options.
