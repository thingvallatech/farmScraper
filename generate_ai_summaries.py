#!/usr/bin/env python3
"""
Generate AI Summaries for Programs
Uses Claude API to create concise 2-3 sentence summaries for each program
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import db
import logging
import time

# Try to import anthropic
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_summary(program_name: str, description: str, eligibility_raw: str, payment_info: str) -> str:
    """Generate a concise summary using Claude API"""

    if not HAS_ANTHROPIC:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return None

    # Get API key from environment
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    # Prepare context
    context = f"""Program Name: {program_name}

Description: {description if description else 'Not available'}

Eligibility: {eligibility_raw[:500] if eligibility_raw else 'Not available'}

Payment Info: {payment_info if payment_info else 'Not available'}"""

    prompt = f"""Please write a concise 2-3 sentence summary of this USDA FSA farm program that would help a farmer quickly understand:
1. What the program does
2. Who it's for
3. Key benefits or purpose

Keep it practical and farmer-focused. Use plain language.

{context}

Summary:"""

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=250,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        summary = message.content[0].text.strip()
        return summary

    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return None


def generate_all_summaries(limit: int = None):
    """Generate summaries for all programs without one"""

    db.connect()

    # Get programs without AI summaries
    query = """
        SELECT
            id,
            program_name,
            description,
            eligibility_raw,
            payment_info_raw
        FROM programs
        WHERE content_type = 'program'
          AND ai_summary IS NULL
          AND confidence_score >= 0.5
        ORDER BY confidence_score DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    programs = db.fetch_all(query)

    logger.info(f"Generating AI summaries for {len(programs)} programs...")

    generated = 0
    for i, program in enumerate(programs):
        logger.info(f"Processing {i+1}/{len(programs)}: {program['program_name']}")

        summary = generate_summary(
            program['program_name'],
            program.get('description', ''),
            program.get('eligibility_raw', ''),
            program.get('payment_info_raw', '')
        )

        if summary:
            db.update(
                'programs',
                {'ai_summary': summary},
                'id = %s',
                (program['id'],)
            )
            generated += 1
            logger.info(f"  ✓ Generated: {summary[:80]}...")
        else:
            logger.warning(f"  ✗ Failed to generate summary")

        # Rate limiting - be respectful of API
        if i < len(programs) - 1:
            time.sleep(1)

    logger.info(f"\n✓ Generated {generated} AI summaries")

    db.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate AI summaries for farm programs')
    parser.add_argument('--limit', type=int, help='Limit number of programs to process')
    parser.add_argument('--test', action='store_true', help='Test mode: only process 3 programs')

    args = parser.parse_args()

    if args.test:
        logger.info("TEST MODE: Processing only 3 programs")
        generate_all_summaries(limit=3)
    else:
        generate_all_summaries(limit=args.limit)
