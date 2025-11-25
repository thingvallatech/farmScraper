#!/usr/bin/env python3
"""
Re-extract Payment Units from Raw Page Text
Fixes programs that have "flat_rate" as payment_unit by looking at source text
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_payment_unit_from_text(text: str, payment_info: str) -> str:
    """
    Extract the payment unit from raw text by looking for patterns like:
    - "$4.00 to $9.50 per hundredweight (cwt)"
    - "$10-$15 per acre"
    - "$5.00 per bushel"
    """
    if not text:
        return "flat_rate"

    # Clean payment info to use in pattern matching
    payment_pattern = re.escape(payment_info).replace(r'\ ', r'\s*')

    # Look for "per [unit]" after the payment range
    # Pattern: payment amount + "per" + unit
    patterns = [
        # "$X to $Y per hundredweight (cwt)"
        rf'{payment_pattern}\s+per\s+(hundredweight|cwt)\b',
        # "$X to $Y per acre"
        rf'{payment_pattern}\s+per\s+(acre|acreage)\b',
        # "$X to $Y per bushel"
        rf'{payment_pattern}\s+per\s+(bushel|bu\.?)\b',
        # "$X to $Y per head"
        rf'{payment_pattern}\s+per\s+(head|animal)\b',
        # "$X to $Y per ton"
        rf'{payment_pattern}\s+per\s+(ton|tonne)\b',
        # "$X to $Y per pound"
        rf'{payment_pattern}\s+per\s+(pound|lb\.?|lbs\.?)\b',
        # General "per X" pattern
        rf'{payment_pattern}\s+per\s+(\w+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            unit = match.group(1).lower()
            # Normalize common units
            if unit in ['hundredweight', 'cwt']:
                return 'cwt'
            elif unit in ['acre', 'acreage']:
                return 'acre'
            elif unit in ['bushel', 'bu', 'bu.']:
                return 'bushel'
            elif unit in ['head', 'animal']:
                return 'head'
            elif unit in ['ton', 'tonne']:
                return 'ton'
            elif unit in ['pound', 'lb', 'lb.', 'lbs', 'lbs.']:
                return 'pound'
            else:
                return unit

    return "flat_rate"


def re_extract_all_units():
    """Re-extract payment units for all programs with flat_rate"""

    db.connect()

    # Get all programs with flat_rate and their source pages
    programs = db.fetch_all("""
        SELECT
            p.id,
            p.program_name,
            p.payment_info_raw,
            p.source_url,
            rp.raw_text
        FROM programs p
        LEFT JOIN raw_pages rp ON p.source_url = rp.url
        WHERE p.payment_unit = 'flat_rate'
          AND p.payment_info_raw IS NOT NULL
          AND rp.raw_text IS NOT NULL
    """)

    logger.info(f"Re-extracting payment units for {len(programs)} programs...")

    updated = 0
    for program in programs:
        old_unit = 'flat_rate'
        new_unit = extract_payment_unit_from_text(
            program['raw_text'],
            program['payment_info_raw']
        )

        if new_unit != 'flat_rate':
            db.update(
                'programs',
                {'payment_unit': new_unit},
                'id = %s',
                (program['id'],)
            )
            updated += 1
            logger.info(f"✓ {program['program_name']}: {old_unit} → {new_unit}")

    logger.info(f"\n✓ Updated {updated}/{len(programs)} programs with proper payment units")

    # Show summary
    units = db.fetch_all("""
        SELECT payment_unit, COUNT(*) as count
        FROM programs
        WHERE payment_min IS NOT NULL
        GROUP BY payment_unit
        ORDER BY count DESC
    """)

    logger.info("\nPayment unit distribution:")
    for row in units:
        logger.info(f"  {row['payment_unit']}: {row['count']}")

    db.close()


if __name__ == '__main__':
    re_extract_all_units()
