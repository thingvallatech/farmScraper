#!/usr/bin/env python3
"""
Database migration script - imports data from local SQL dump
"""
import os
import sys
from src.database.connection import db

def import_sql_file(sql_file_path):
    """Import SQL file into the database"""
    print(f"Reading SQL file: {sql_file_path}")

    with open(sql_file_path, 'r') as f:
        sql_content = f.read()

    print(f"SQL file size: {len(sql_content)} characters")

    # Split into individual statements and execute
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]

    print(f"Executing {len(statements)} SQL statements...")

    db.connect()

    try:
        for i, statement in enumerate(statements):
            if statement:
                try:
                    db.execute(statement)
                    if (i + 1) % 100 == 0:
                        print(f"Executed {i + 1}/{len(statements)} statements...")
                except Exception as e:
                    print(f"Error on statement {i + 1}: {e}")
                    if "already exists" not in str(e).lower():
                        raise

        print("Database import completed successfully!")

        # Verify import
        programs = db.fetch_one("SELECT COUNT(*) as count FROM programs WHERE content_type = 'program'")
        print(f"Total programs in database: {programs['count']}")

    finally:
        db.close()

if __name__ == "__main__":
    sql_file = "/tmp/farm_scraper_dump.sql"

    if not os.path.exists(sql_file):
        print(f"Error: SQL file not found at {sql_file}")
        sys.exit(1)

    import_sql_file(sql_file)
