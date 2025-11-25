#!/usr/bin/env python3
"""
Parse Detailed Eligibility Requirements
Extracts specific, checkable requirements from eligibility text
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_requirements(eligibility_text: str, program_name: str) -> dict:
    """Extract detailed eligibility requirements that can be checked off"""

    if not eligibility_text:
        return {}

    text_lower = eligibility_text.lower()
    requirements = []

    # Citizenship requirements
    if 'u.s. citizen' in text_lower or 'united states citizen' in text_lower:
        requirements.append({
            'category': 'citizenship',
            'requirement': 'Must be a U.S. citizen, non-citizen national, or qualified alien',
            'type': 'boolean',
            'key': 'is_us_citizen'
        })

    # Age requirements
    age_match = re.search(r'age[ds]?\s+(\d+)\s+to\s+(\d+)', text_lower)
    if age_match:
        min_age, max_age = age_match.groups()
        requirements.append({
            'category': 'age',
            'requirement': f'Must be between {min_age} and {max_age} years old',
            'type': 'range',
            'key': 'age',
            'min': int(min_age),
            'max': int(max_age)
        })

    # Beginning farmer
    if 'beginning farmer' in text_lower:
        requirements.append({
            'category': 'farmer_status',
            'requirement': 'Must be a beginning farmer (farming for less than 10 years)',
            'type': 'boolean',
            'key': 'is_beginning_farmer',
            'priority': True
        })

    # Small farm operator
    if 'small' in text_lower and ('farm' in text_lower or 'operator' in text_lower):
        requirements.append({
            'category': 'farm_size',
            'requirement': 'Must be a small or family farm operation',
            'type': 'boolean',
            'key': 'is_small_farm'
        })

    # Credit history
    if 'credit history' in text_lower or 'satisfactory credit' in text_lower:
        requirements.append({
            'category': 'credit',
            'requirement': 'Must demonstrate satisfactory credit history',
            'type': 'boolean',
            'key': 'has_satisfactory_credit'
        })

    # Ability to repay
    if 'ability to repay' in text_lower or 'repay the loan' in text_lower:
        requirements.append({
            'category': 'financial',
            'requirement': 'Must demonstrate ability to repay the loan',
            'type': 'boolean',
            'key': 'can_repay_loan'
        })

    # Cannot obtain credit elsewhere
    if 'unable to obtain' in text_lower or 'cannot obtain' in text_lower:
        requirements.append({
            'category': 'credit',
            'requirement': 'Unable to obtain credit elsewhere at reasonable rates',
            'type': 'boolean',
            'key': 'cannot_get_commercial_credit'
        })

    # AGI/Income limits
    agi_match = re.search(r'\$(\d{1,3}(?:,\d{3})*)\s*(?:agi|income|gross.*income)', text_lower)
    if agi_match or 'income limit' in text_lower or 'agi' in text_lower:
        requirements.append({
            'category': 'income',
            'requirement': 'Must meet income/AGI limits (typically under $900,000)',
            'type': 'threshold',
            'key': 'meets_agi_limit',
            'note': 'Verify specific limit for this program with FSA office'
        })

    # Conservation compliance
    if 'conservation plan' in text_lower or 'conservation compliance' in text_lower:
        requirements.append({
            'category': 'conservation',
            'requirement': 'Must be in compliance with conservation requirements',
            'type': 'boolean',
            'key': 'has_conservation_plan'
        })

    # Veteran status
    if 'veteran' in text_lower:
        requirements.append({
            'category': 'farmer_status',
            'requirement': 'Must be a veteran farmer',
            'type': 'boolean',
            'key': 'is_veteran',
            'priority': True
        })

    # Socially disadvantaged
    if 'socially disadvantaged' in text_lower or 'minority' in text_lower:
        requirements.append({
            'category': 'farmer_status',
            'requirement': 'Must be a socially disadvantaged farmer',
            'type': 'boolean',
            'key': 'is_socially_disadvantaged',
            'priority': True
        })

    # Youth organization (for youth loans)
    if 'youth organization' in text_lower or 'ffa' in text_lower or '4-h' in text_lower:
        requirements.append({
            'category': 'membership',
            'requirement': 'Must participate in approved agricultural youth organization (FFA, 4-H)',
            'type': 'boolean',
            'key': 'in_youth_org'
        })

    # Native American (for tribal programs)
    if 'native american' in text_lower or 'tribal' in text_lower or 'indian land' in text_lower:
        requirements.append({
            'category': 'special',
            'requirement': 'Must be Native American landowner or tribal entity',
            'type': 'boolean',
            'key': 'is_native_american'
        })

    # Farm ownership/operation requirements
    if 'own' in text_lower or 'operate' in text_lower:
        if 'own and operate' in text_lower:
            requirements.append({
                'category': 'farm_ownership',
                'requirement': 'Must own and operate a farm',
                'type': 'boolean',
                'key': 'owns_and_operates_farm'
            })
        elif 'owner' in text_lower and 'operator' not in text_lower:
            requirements.append({
                'category': 'farm_ownership',
                'requirement': 'Must be a farm owner',
                'type': 'boolean',
                'key': 'is_farm_owner'
            })
        elif 'operator' in text_lower or 'operate' in text_lower:
            requirements.append({
                'category': 'farm_ownership',
                'requirement': 'Must operate a farm (ownership not required)',
                'type': 'boolean',
                'key': 'operates_farm'
            })

    # Active farming requirement
    if 'actively' in text_lower and 'farm' in text_lower:
        requirements.append({
            'category': 'active_farming',
            'requirement': 'Must be actively engaged in farming',
            'type': 'boolean',
            'key': 'actively_farming'
        })

    # Acres requirements
    acre_matches = re.finditer(r'(\d+)\s*(?:acre|ac\b)', text_lower)
    for match in acre_matches:
        acres = match.group(1)
        requirements.append({
            'category': 'acres',
            'requirement': f'May have acreage requirements (reference: {acres} acres mentioned)',
            'type': 'info',
            'key': 'acres_requirement',
            'note': 'Verify specific acreage requirement with FSA office'
        })
        break  # Only add once

    return {
        'requirements': requirements,
        'total_requirements': len([r for r in requirements if r['type'] != 'info'])
    }


def parse_all_programs():
    """Parse requirements for all programs"""

    db.connect()

    # Get programs with eligibility text
    programs = db.fetch_all("""
        SELECT
            id,
            program_name,
            eligibility_raw
        FROM programs
        WHERE eligibility_raw IS NOT NULL
          AND confidence_score >= 0.5
        ORDER BY confidence_score DESC
    """)

    logger.info(f"Parsing detailed requirements for {len(programs)} programs...")

    # Add new column if it doesn't exist
    db.execute("""
        ALTER TABLE programs
        ADD COLUMN IF NOT EXISTS eligibility_requirements JSONB
    """)

    updated = 0
    for program in programs:
        requirements_data = extract_requirements(
            program['eligibility_raw'],
            program['program_name']
        )

        if requirements_data['requirements']:
            db.update(
                'programs',
                {'eligibility_requirements': requirements_data},
                'id = %s',
                (program['id'],)
            )
            updated += 1

            if updated % 10 == 0:
                logger.info(f"Processed {updated}/{len(programs)} programs...")

    logger.info(f"✓ Parsed detailed requirements for {updated} programs")

    # Show sample
    sample = db.fetch_one("""
        SELECT
            program_name,
            jsonb_pretty(eligibility_requirements) as requirements
        FROM programs
        WHERE eligibility_requirements IS NOT NULL
        ORDER BY (eligibility_requirements->>'total_requirements')::int DESC
        LIMIT 1
    """)

    if sample:
        logger.info(f"\nSample requirements for '{sample['program_name']}':")
        logger.info(sample['requirements'])

    db.close()


if __name__ == '__main__':
    parse_all_programs()
