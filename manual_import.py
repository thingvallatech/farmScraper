#!/usr/bin/env python3
"""
One-time script to manually import the SQL dump to the database.
This should be run once after deployment, then can be deleted.
"""
import os
import sys
import requests
import subprocess
import tempfile
from urllib.parse import urlparse

def main():
    # Get the SQL dump URL
    sql_dump_url = os.getenv('SQL_DUMP_URL', 'https://github.com/thingvallatech/farmScraper/releases/download/v1.0.0-db-seed/farm_scraper_dump.sql')
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print('ERROR: DATABASE_URL environment variable not set')
        sys.exit(1)

    print(f'Downloading SQL dump from {sql_dump_url}...')
    response = requests.get(sql_dump_url, timeout=300)
    response.raise_for_status()
    sql_content = response.text
    print(f'Downloaded {len(sql_content)} bytes ({len(sql_content)/1024/1024:.1f} MB)')

    # Write SQL content to temporary file
    print('Writing SQL dump to temporary file...')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
        temp_file = f.name
        f.write(sql_content)

    print(f'Importing SQL dump using psql...')
    try:
        # Use psql to import the dump - it properly handles COPY statements
        env = os.environ.copy()
        env['PGPASSWORD'] = urlparse(database_url).password

        result = urlparse(database_url)
        cmd = [
            'psql',
            '-h', result.hostname,
            '-p', str(result.port or 5432),
            '-U', result.username,
            '-d', result.path.lstrip('/'),
            '-f', temp_file,
            '--set', 'ON_ERROR_STOP=off'  # Continue on errors
        ]

        # Add sslmode if required
        if 'sslmode=require' in database_url:
            env['PGSSLMODE'] = 'require'

        print(f'Running: psql -h {result.hostname} -U {result.username} -d {result.path.lstrip("/")} -f {temp_file}')

        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Stream output in real-time
        for line in process.stdout:
            print(line.rstrip())

        process.wait()

        if process.returncode != 0:
            print(f'Warning: psql exited with code {process.returncode}')
        else:
            print('Successfully imported SQL dump')

    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.unlink(temp_file)
            print(f'Cleaned up temporary file')

if __name__ == '__main__':
    main()
