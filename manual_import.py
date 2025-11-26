#!/usr/bin/env python3
"""
One-time script to manually import the SQL dump to the database.
This should be run once after deployment, then can be deleted.
"""
import os
import sys
import requests
import psycopg2
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
    print(f'Downloaded {len(sql_content)} bytes')

    # Parse database URL
    result = urlparse(database_url)

    print('Connecting to database...')
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port or 5432,
        user=result.username,
        password=result.password,
        database=result.path.lstrip('/'),
        sslmode='require' if 'sslmode=require' in database_url else 'prefer'
    )

    print('Importing SQL dump...')
    cursor = conn.cursor()

    # Split SQL into statements and execute
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
    total = len(statements)

    for i, statement in enumerate(statements, 1):
        if i % 100 == 0:
            print(f'Progress: {i}/{total} statements ({i*100//total}%)')
        try:
            cursor.execute(statement)
        except Exception as e:
            print(f'Warning: Error executing statement {i}: {e}')

    conn.commit()
    cursor.close()
    conn.close()

    print(f'Successfully imported {total} SQL statements')

if __name__ == '__main__':
    main()
