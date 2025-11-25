#!/usr/bin/env python3
"""
Clean up program data - remove duplicates and low-quality entries
"""
import logging
from src.logging_config import setup_logging
from src.database.connection import db

setup_logging()
logger = logging.getLogger(__name__)


def cleanup_programs():
    """Remove low-quality and duplicate program entries"""

    db.connect()

    try:
        # Step 1: Delete navigation pages
        logger.info("Step 1: Removing navigation pages...")
        query = """
            DELETE FROM programs
            WHERE program_name LIKE '%Find a Program%'
               OR program_name LIKE '%Find Loans%'
               OR program_name LIKE '%Programs and Services%'
            RETURNING id;
        """
        deleted = db.fetch_all(query)
        logger.info(f"Deleted {len(deleted)} navigation pages")

        # Step 2: Delete very low confidence entries
        logger.info("Step 2: Removing very low confidence entries...")
        query = """
            DELETE FROM programs
            WHERE confidence_score < 0.3
            RETURNING id;
        """
        deleted = db.fetch_all(query)
        logger.info(f"Deleted {len(deleted)} very low confidence entries")

        # Step 3: Remove duplicate URLs (keep canonical URL without # anchor)
        logger.info("Step 3: Deduplicating URLs with # anchors...")
        query = """
            DELETE FROM programs p1
            WHERE source_url LIKE '%#%'
              AND EXISTS (
                  SELECT 1 FROM programs p2
                  WHERE p2.program_name = p1.program_name
                    AND p2.source_url = SPLIT_PART(p1.source_url, '#', 1)
              )
            RETURNING id;
        """
        deleted = db.fetch_all(query)
        logger.info(f"Deleted {len(deleted)} duplicate anchor URLs")

        # Step 4: For remaining duplicates, keep the one with highest confidence
        logger.info("Step 4: Removing lower-confidence duplicates...")
        query = """
            DELETE FROM programs p1
            WHERE id NOT IN (
                SELECT DISTINCT ON (program_name) id
                FROM programs
                ORDER BY program_name, confidence_score DESC, id
            )
            RETURNING id;
        """
        deleted = db.fetch_all(query)
        logger.info(f"Deleted {len(deleted)} lower-confidence duplicates")

        # Step 5: Delete obvious news articles
        logger.info("Step 5: Removing news articles...")
        query = """
            DELETE FROM programs
            WHERE (program_name LIKE 'USDA %' OR program_name LIKE 'Secretary %')
              AND program_name NOT LIKE '%Program%'
              AND program_name NOT LIKE '%Loan%'
              AND confidence_score < 0.6
            RETURNING id;
        """
        deleted = db.fetch_all(query)
        logger.info(f"Deleted {len(deleted)} news articles")

        # Summary
        query = "SELECT COUNT(*) as count FROM programs"
        result = db.fetch_one(query)
        total = result['count']

        logger.info("=" * 60)
        logger.info(f"Cleanup complete! {total} quality programs remaining")
        logger.info("=" * 60)

        # Show breakdown by confidence
        query = """
            SELECT
              CASE
                WHEN confidence_score >= 0.7 THEN 'High (0.7+)'
                WHEN confidence_score >= 0.5 THEN 'Medium (0.5-0.7)'
                ELSE 'Low (<0.5)'
              END as quality,
              COUNT(*) as count
            FROM programs
            GROUP BY quality
            ORDER BY MIN(confidence_score) DESC;
        """
        results = db.fetch_all(query)

        logger.info("Quality breakdown:")
        for row in results:
            logger.info(f"  {row['quality']}: {row['count']} programs")

        print("\n" + "=" * 60)
        print(f"✅ Cleanup complete! {total} quality programs remaining")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    cleanup_programs()
