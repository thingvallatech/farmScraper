#!/bin/bash
set -e

echo "=== FSA Program Explorer Startup ==="
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting entrypoint script"

# Wait for database to be ready
echo "$(date '+%Y-%m-%d %H:%M:%S') - Waiting for database to be ready..."

# Disable exit on error for database check
set +e
python3 -c "
import time
import os
import sys
import psycopg2
from urllib.parse import urlparse

print('Checking DATABASE_URL environment variable...')
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)

print('DATABASE_URL is set, parsing connection details...')
result = urlparse(database_url)
print(f'Database host: {result.hostname}')
print(f'Database port: {result.port or 5432}')
print(f'Database name: {result.path.lstrip(\"/\")}')

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        print(f'Attempting to connect (attempt {retry_count + 1}/{max_retries})...')
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
        sys.exit(0)
    except Exception as e:
        retry_count += 1
        if retry_count < max_retries:
            print(f'Database not ready yet (attempt {retry_count}/{max_retries}): {e}')
            time.sleep(2)
        else:
            print(f'ERROR: Could not connect to database after {max_retries} attempts: {e}')
            sys.exit(1)
"
DB_CHECK_EXIT=$?
set -e

if [ $DB_CHECK_EXIT -ne 0 ]; then
    echo "ERROR: Database check failed with exit code $DB_CHECK_EXIT"
    exit $DB_CHECK_EXIT
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Database connection successful"

# Check if database needs to be initialized
echo "$(date '+%Y-%m-%d %H:%M:%S') - Checking if database has data..."

set +e
PROGRAM_COUNT=$(python3 -c "
import os
import sys
import psycopg2
from urllib.parse import urlparse

print('Connecting to database to check program count...')
database_url = os.getenv('DATABASE_URL')
result = urlparse(database_url)

try:
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
        print('Querying programs table...')
        cursor.execute(\"SELECT COUNT(*) FROM programs WHERE content_type = 'program'\")
        count = cursor.fetchone()[0]
        print(f'Found {count} programs')
        print(count)
    except Exception as e:
        # Table doesn't exist yet
        print(f'Programs table does not exist yet: {e}')
        print(0)
    finally:
        cursor.close()
        conn.close()
except Exception as e:
    print(f'ERROR checking program count: {e}')
    print(0)
" 2>&1 | tail -1)
CHECK_EXIT=$?
set -e

echo "$(date '+%Y-%m-%d %H:%M:%S') - Found $PROGRAM_COUNT programs in database"

# Log database status - import will happen in Flask app
if [ "$PROGRAM_COUNT" -eq "0" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Database is empty ($PROGRAM_COUNT programs)"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Import will be triggered by Flask app on first request"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Database already has $PROGRAM_COUNT programs"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - ==================================="
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting application"
echo "$(date '+%Y-%m-%d %H:%M:%S') - ==================================="
# Start the application
exec "$@"
