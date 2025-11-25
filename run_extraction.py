#!/usr/bin/env python3
"""
Run program extraction on discovered pages
"""
import asyncio
import logging
from src.logging_config import setup_logging
from src.scrapers.extractor import process_discovered_pages
from src.database.connection import db

setup_logging()
logger = logging.getLogger(__name__)

async def main():
    logger.info('Running program extraction on all discovered pages...')
    db.connect()
    try:
        await process_discovered_pages()

        # Check results
        count = db.fetch_one('SELECT COUNT(*) as count FROM programs')
        logger.info(f'Extraction complete: {count["count"]} programs found')
        print(f'\n========================================')
        print(f'Programs extracted: {count["count"]}')
        print(f'========================================')
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
