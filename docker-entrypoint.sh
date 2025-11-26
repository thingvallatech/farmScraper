#!/bin/bash
set -e

echo "=== FSA Program Explorer Startup ==="

# Wait for database to be ready
echo "Waiting for database to be ready..."
python3 -c "
import time
import os
import psycopg2
from urllib.parse import urlparse

max_retries = 30
retry_count = 0

database_url = os.getenv('DATABASE_URL')
if not database_url:
    print('ERROR: DATABASE_URL not set')
    exit(1)

result = urlparse(database_url)

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port or 5432,
            user=result.username,
            password=result.password,
            database=result.path.lstrip('/'),
            sslmode='require' if 'sslmode=require' in database_url else 'prefer'
        )
        conn.close()
        print('Database is ready!')
        break
    except Exception as e:
        retry_count += 1
        if retry_count < max_retries:
            print(f'Database not ready yet (attempt {retry_count}/{max_retries}), waiting...')
            time.sleep(2)
        else:
            print(f'ERROR: Could not connect to database after {max_retries} attempts: {e}')
            exit(1)
"

# Check if database needs to be initialized
echo "Checking if database has data..."
PROGRAM_COUNT=$(python3 -c "
import os
import psycopg2
from urllib.parse import urlparse

database_url = os.getenv('DATABASE_URL')
result = urlparse(database_url)

conn = psycopg2.connect(
    host=result.hostname,
    port=result.port or 5432,
    user=result.username,
    password=result.password,
    database=result.path.lstrip('/'),
    sslmode='require' if 'sslmode=require' in database_url else 'prefer'
)

cursor = conn.cursor()
try:
    cursor.execute(\"SELECT COUNT(*) FROM programs WHERE content_type = 'program'\")
    count = cursor.fetchone()[0]
    print(count)
except Exception:
    # Table doesn't exist yet
    print(0)
finally:
    cursor.close()
    conn.close()
")

echo "Found $PROGRAM_COUNT programs in database"

# Use default SQL dump URL if not set
if [ -z "$SQL_DUMP_URL" ]; then
    SQL_DUMP_URL="https://github.com/thingvallatech/farmScraper/releases/download/v1.0.0-db-seed/farm_scraper_dump.sql"
    echo "Using default SQL_DUMP_URL: $SQL_DUMP_URL"
fi

# If database is empty and SQL_DUMP_URL is provided, import data
if [ "$PROGRAM_COUNT" -eq "0" ] && [ -n "$SQL_DUMP_URL" ]; then
    echo "=== Database is empty - importing data from $SQL_DUMP_URL ==="

    # Download SQL dump
    echo "Downloading SQL dump..."
    curl -L -o /tmp/farm_scraper_dump.sql "$SQL_DUMP_URL"

    if [ -f /tmp/farm_scraper_dump.sql ]; then
        echo "SQL dump downloaded successfully ($(du -h /tmp/farm_scraper_dump.sql | cut -f1))"

        # Import using the import_db.py script
        echo "Importing data..."
        python3 import_db.py

        # Clean up
        rm -f /tmp/farm_scraper_dump.sql
        echo "Database import completed!"
    else
        echo "WARNING: Failed to download SQL dump from $SQL_DUMP_URL"
    fi
elif [ "$PROGRAM_COUNT" -eq "0" ]; then
    echo "WARNING: Database is empty but SQL_DUMP_URL is not set. Skipping import."
    echo "To enable automatic import, set the SQL_DUMP_URL environment variable."
else
    echo "Database already has data. Skipping import."
fi

echo "=== Starting application ==="
# Start the application
exec "$@"
