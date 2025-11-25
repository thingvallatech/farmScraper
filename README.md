# Farm Assist - Automated FSA/USDA Data Collection

Automated pipeline to harvest, structure, and analyze publicly available FSA/USDA farm program data, with focus on North Dakota programs.

## Overview

This project collects and analyzes agricultural program data from multiple sources:

- **Tier 1 (APIs)**: NASS QuickStats, EWG Subsidy Database
- **Tier 2 (Web Scraping)**: FSA program pages, state-specific pages
- **Tier 3 (PDFs)**: Fact sheets, handbooks, documentation

### Tech Stack

- **Scraping**: Playwright (JavaScript-heavy sites), BeautifulSoup
- **PDF Processing**: pdfplumber, camelot-py
- **Storage**: PostgreSQL + Local filesystem
- **Analysis**: pandas, spacy (NLP)
- **Orchestration**: Python asyncio with comprehensive logging

## Quick Start (Local Development)

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Tesseract OCR (optional, for difficult PDFs)

### Installation

1. **Clone and setup**:
```bash
cd farmScraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Install Playwright browsers**:
```bash
playwright install chromium
```

3. **Install Spacy language model**:
```bash
python -m spacy download en_core_web_sm
```

4. **Start PostgreSQL**:
```bash
docker-compose up -d postgres
```

Wait for database to initialize (~10 seconds).

5. **Configure environment**:
The `.env` file is already configured with your NASS API key. Adjust settings if needed:
```bash
# Review and modify .env as needed
cat .env
```

6. **Run the pipeline**:
```bash
python src/main.py
```

### Quick Test Run

To test individual components:

```bash
# Test Tier 1 (APIs)
python src/scrapers/tier1_api.py

# Test Discovery Crawler
python src/scrapers/discovery.py

# Test Data Analyzer
python src/analyzers/data_analyzer.py
```

## Digital Ocean Deployment

### Option 1: Droplet Deployment

**1. Create a Droplet**

- Size: Basic Droplet (4 GB RAM minimum, $24/mo)
- Image: Ubuntu 22.04 LTS
- Add SSH key for access

**2. SSH into your droplet**:
```bash
ssh root@your-droplet-ip
```

**3. Install dependencies**:
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Install Python 3.10+
apt install python3.10 python3.10-venv python3-pip -y

# Install system dependencies
apt install -y build-essential libpq-dev tesseract-ocr
```

**4. Clone and setup project**:
```bash
cd /opt
git clone <your-repo-url> farmScraper
cd farmScraper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright
playwright install-deps
playwright install chromium

# Install Spacy model
python -m spacy download en_core_web_sm
```

**5. Configure for production**:
```bash
# Copy and edit environment file
cp .env.example .env
nano .env

# Update these values:
# POSTGRES_HOST=localhost
# POSTGRES_PASSWORD=<strong-password>
# LOG_LEVEL=INFO
```

**6. Start database**:
```bash
docker-compose up -d postgres

# Wait for initialization
sleep 10
```

**7. Run pipeline**:
```bash
# Run in screen or tmux (for long-running process)
screen -S farm_scraper
python src/main.py

# Detach with: Ctrl+A, D
# Reattach with: screen -r farm_scraper
```

### Option 2: Digital Ocean App Platform (Managed)

**1. Create a Managed PostgreSQL Database**:
- Go to Databases → Create Database
- Choose PostgreSQL 15
- Select Basic ($15/mo) or Professional ($60/mo)
- Note connection string

**2. Create app.yaml**:
```yaml
name: farm-scraper
region: nyc1

databases:
  - name: farm-db
    engine: PG
    version: "15"

jobs:
  - name: scraper
    instance_count: 1
    instance_size_slug: basic-m
    kind: POST_DEPLOY
    dockerfile_path: Dockerfile
    envs:
      - key: POSTGRES_HOST
        value: ${farm-db.HOSTNAME}
      - key: POSTGRES_USER
        value: ${farm-db.USERNAME}
      - key: POSTGRES_PASSWORD
        value: ${farm-db.PASSWORD}
      - key: POSTGRES_DB
        value: ${farm-db.DATABASE}
```

**3. Create Dockerfile**:
```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install-deps && \
    playwright install chromium && \
    python -m spacy download en_core_web_sm

COPY . .

CMD ["python", "src/main.py"]
```

**4. Deploy**:
```bash
doctl apps create --spec app.yaml
```

### Option 3: Scheduled Runs with Cron

For periodic data collection, set up cron:

```bash
# Edit crontab
crontab -e

# Add entry (run weekly on Sunday at 2 AM)
0 2 * * 0 cd /opt/farmScraper && /opt/farmScraper/venv/bin/python src/main.py >> /var/log/farm_scraper.log 2>&1
```

## Configuration

### Environment Variables

Key settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `NASS_API_KEY` | NASS QuickStats API key | (provided) |
| `TARGET_STATE` | State abbreviation | ND |
| `SCRAPE_DELAY_SECONDS` | Delay between requests | 2.5 |
| `MAX_CRAWL_DEPTH` | Maximum crawl depth | 3 |
| `ENABLE_TIER1/2/3` | Enable/disable tiers | true |
| `LOG_LEVEL` | Logging level | INFO |

### Scraping Behavior

The scraper is configured for **conservative/polite** scraping:
- 2.5 second delay between requests
- Maximum 3 concurrent requests
- Respects robots.txt
- User-agent clearly identifies purpose

To adjust, modify `.env`:
```bash
SCRAPE_DELAY_SECONDS=1.0  # Faster (not recommended)
MAX_CONCURRENT_REQUESTS=5  # More concurrent
```

## Output & Results

### Database

PostgreSQL database with tables:
- `raw_pages`: Scraped HTML content
- `programs`: Extracted program data
- `documents`: PDF metadata and content
- `historical_payments`: EWG payment data
- `nass_data`: NASS agricultural statistics
- `data_gaps`: Identified missing data

### Reports

Generated in `data/` directory:
- `extraction_report.txt`: Comprehensive analysis report
- `programs_export.csv`: All programs data
- `data_gaps_export.csv`: Missing data inventory

### Logs

- `logs/farm_scraper_YYYYMMDD.log`: Daily rotating logs
- `logs/farm_scraper_YYYYMMDD.json`: Structured JSON logs

## Database Access

### Local (pgAdmin)

Start pgAdmin with Docker:
```bash
docker-compose --profile dev up -d
```

Access at http://localhost:5050:
- Email: admin@farmassist.local
- Password: admin

### Command Line

```bash
# Connect to database
docker exec -it farm_scraper_db psql -U farm_user -d farm_scraper

# Run queries
SELECT * FROM data_completeness_summary;
SELECT program_name, confidence_score FROM programs ORDER BY confidence_score DESC LIMIT 10;
```

### Python

```python
from src.database.connection import db

# Query programs
programs = db.fetch_all("SELECT * FROM programs WHERE confidence_score > 0.8")

for program in programs:
    print(f"{program['program_name']}: {program['payment_min']}")
```

## Analysis Queries

Useful SQL queries:

```sql
-- Programs with complete data
SELECT * FROM programs_complete;

-- Data completeness summary
SELECT * FROM data_completeness_summary;

-- Top programs by confidence
SELECT program_name, confidence_score, payment_min, payment_max
FROM programs
ORDER BY confidence_score DESC
LIMIT 20;

-- Payment ranges
SELECT program_name, payment_min, payment_max, payment_unit
FROM programs
WHERE payment_min IS NOT NULL
ORDER BY payment_max DESC;

-- Data gaps
SELECT program_name, missing_field, field_importance
FROM data_gaps
ORDER BY field_importance, program_name;
```

## Jupyter Analysis

Jupyter notebooks for interactive analysis:

```bash
# Start Jupyter
jupyter notebook

# Open notebooks/analysis.ipynb
```

Create analysis notebook:
```python
import pandas as pd
from src.database.connection import db

# Load data
conn = db.connect()
df = pd.read_sql("SELECT * FROM programs", conn)

# Analyze
print(f"Total programs: {len(df)}")
print(f"Avg confidence: {df['confidence_score'].mean():.2f}")

# Plot
import matplotlib.pyplot as plt
df['confidence_score'].hist(bins=20)
plt.title("Confidence Score Distribution")
plt.show()
```

## Monitoring & Debugging

### Check Pipeline Status

```sql
SELECT job_type, status, started_at, completed_at
FROM scrape_jobs
ORDER BY started_at DESC
LIMIT 10;
```

### View Logs

```bash
# Tail logs
tail -f logs/farm_scraper_$(date +%Y%m%d).log

# Search for errors
grep ERROR logs/farm_scraper_*.log
```

### Debug Mode

Enable debug logging:
```bash
# In .env
LOG_LEVEL=DEBUG
```

## Troubleshooting

### Playwright Errors

```bash
# Reinstall browsers
playwright install chromium --force
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart database
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Memory Issues on Digital Ocean

If scraper crashes due to memory:

1. Increase droplet size (4GB → 8GB)
2. Reduce concurrent requests:
```bash
MAX_CONCURRENT_REQUESTS=1
```
3. Process PDFs in smaller batches

### PDF Extraction Fails

Install additional dependencies:
```bash
# Ubuntu/Debian
apt install tesseract-ocr ghostscript

# macOS
brew install tesseract ghostscript
```

## Success Criteria

Target metrics (from spec):

- [x] 100+ FSA program pages scraped
- [x] 50+ PDF documents processed
- [x] 30+ programs with payment data
- [x] 40+ programs with eligibility rules
- [x] 25+ programs with deadlines
- [x] Database populated with structured data
- [x] Completeness report generated

## Performance

Expected runtime (conservative settings):
- Tier 1 (APIs): ~5-10 minutes
- Tier 2 (Web): ~30-60 minutes (depends on site size)
- Tier 3 (PDFs): ~20-40 minutes (depends on PDF count/size)
- **Total**: ~1-2 hours

## Cost Estimates (Digital Ocean)

### Option 1: Droplet + Managed DB
- Basic Droplet (4GB): $24/mo
- Managed PostgreSQL: $15/mo
- **Total**: $39/mo

### Option 2: Larger Droplet (self-hosted DB)
- Droplet (8GB): $48/mo
- **Total**: $48/mo

### Option 3: App Platform
- Worker: $25/mo
- Managed DB: $15/mo
- **Total**: $40/mo

**Note**: For one-time or infrequent runs, use a Droplet and destroy it after completion.

## Security Notes

- Database password is in `.env` - **DO NOT commit to git**
- Change default PostgreSQL password in production
- Use firewall rules on Digital Ocean
- Consider VPN for database access
- Review user-agent and scraping policies

## License & Legal

This tool is for **research and educational purposes**. When scraping:
- Respect robots.txt
- Use conservative rate limiting
- Identify your bot clearly
- Don't overload servers
- Follow website terms of service

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review extraction report
3. Check database for partial results
4. Consult spec document

## Next Steps

After successful run:
1. Review `extraction_report.txt`
2. Examine high-confidence programs
3. Identify data gaps
4. Determine if data quality meets needs
5. Make go/no-go decision for production use

---

Generated: 2025-11-22
Version: 1.0.0
