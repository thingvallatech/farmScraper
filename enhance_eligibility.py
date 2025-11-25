#!/usr/bin/env python3
"""
Enhanced Eligibility Parser
Extracts structured criteria from program eligibility text to help farmers find matching programs
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_enhanced_criteria(eligibility_text: str, program_name: str, description: str = "") -> dict:
    """Extract detailed, farmer-focused criteria from eligibility text"""

    if not eligibility_text:
        return {}

    text_lower = (eligibility_text + " " + program_name + " " + (description or "")).lower()

    criteria = {
        # Farm Type / Operations (General)
        'crop_farming': any(keyword in text_lower for keyword in [
            'crop', 'grain', 'wheat', 'corn', 'soybean', 'cotton', 'rice', 'acres', 'planted'
        ]),
        'livestock': any(keyword in text_lower for keyword in [
            'livestock', 'cattle', 'beef', 'dairy', 'hog', 'swine', 'sheep', 'goat', 'poultry', 'chicken', 'animal'
        ]),
        'dairy': 'dairy' in text_lower,
        'organic': 'organic' in text_lower,
        'specialty_crops': any(keyword in text_lower for keyword in [
            'fruit', 'vegetable', 'specialty crop', 'horticulture', 'nursery'
        ]),

        # Specific Livestock Types
        'livestock_beef_cattle': any(keyword in text_lower for keyword in [
            'beef cattle', 'beef', 'cow-calf', 'feeder cattle', 'stocker'
        ]),
        'livestock_dairy_cattle': 'dairy' in text_lower,
        'livestock_hogs': any(keyword in text_lower for keyword in [
            'hog', 'swine', 'pig', 'pork'
        ]),
        'livestock_poultry': any(keyword in text_lower for keyword in [
            'poultry', 'chicken', 'turkey', 'broiler', 'layer', 'egg'
        ]),
        'livestock_sheep_goats': any(keyword in text_lower for keyword in [
            'sheep', 'goat', 'lamb', 'wool', 'mohair', 'kid'
        ]),
        'livestock_bees': any(keyword in text_lower for keyword in [
            'bee', 'honey', 'apiculture', 'pollinator', 'hive'
        ]),
        'livestock_aquaculture': any(keyword in text_lower for keyword in [
            'fish', 'aquaculture', 'catfish', 'trout', 'tilapia', 'shrimp'
        ]),

        # Farmer Status
        'beginning_farmer': any(keyword in text_lower for keyword in [
            'beginning farmer', 'new farmer', 'first-time farmer', 'socially disadvantaged'
        ]),
        'veteran': 'veteran' in text_lower or 'military' in text_lower,
        'young_farmer': 'young' in text_lower or 'youth' in text_lower,
        'socially_disadvantaged': 'socially disadvantaged' in text_lower or 'minority' in text_lower,

        # Program Type
        'is_loan': any(keyword in text_lower for keyword in [
            'loan', 'financing', 'borrow', 'credit'
        ]),
        'is_insurance': 'insurance' in text_lower or 'risk management' in text_lower,
        'is_payment': any(keyword in text_lower for keyword in [
            'payment', 'subsidy', 'assistance', 'compensation'
        ]),
        'is_conservation': any(keyword in text_lower for keyword in [
            'conservation', 'environmental', 'soil health', 'water quality', 'crp', 'csp', 'eqip'
        ]),
        'is_disaster': any(keyword in text_lower for keyword in [
            'disaster', 'emergency', 'drought', 'flood', 'hurricane', 'wildfire', 'pandemic'
        ]),

        # Requirements
        'requires_ownership': any(keyword in text_lower for keyword in [
            'owner', 'ownership', 'own the land', 'land owner'
        ]),
        'allows_tenants': any(keyword in text_lower for keyword in [
            'tenant', 'renter', 'lease', 'landlord'
        ]),
        'requires_acreage': bool(re.search(r'\d+\s*acre', text_lower)),
        'requires_revenue': bool(re.search(r'\$[\d,]+', text_lower) or 'income' in text_lower),
        'requires_conservation_plan': any(keyword in text_lower for keyword in [
            'conservation plan', 'conservation compliance'
        ]),

        # Specific Situations
        'for_price_loss': 'price loss' in text_lower or 'market loss' in text_lower,
        'for_yield_loss': 'yield loss' in text_lower or 'crop loss' in text_lower,
        'for_forage_loss': 'forage' in text_lower and 'loss' in text_lower,
        'for_tree_loss': 'tree' in text_lower and ('loss' in text_lower or 'damage' in text_lower),
        'for_equipment': 'equipment' in text_lower or 'machinery' in text_lower,
        'for_storage': 'storage' in text_lower or 'facility' in text_lower,
        'for_land_purchase': 'purchase' in text_lower and 'land' in text_lower,

        # Specific Crop Types
        'crop_wheat': 'wheat' in text_lower,
        'crop_corn': 'corn' in text_lower or 'maize' in text_lower,
        'crop_soybeans': 'soybean' in text_lower or 'soy bean' in text_lower,
        'crop_cotton': 'cotton' in text_lower,
        'crop_rice': 'rice' in text_lower,
        'crop_barley': 'barley' in text_lower,
        'crop_sorghum': 'sorghum' in text_lower or 'milo' in text_lower,
        'crop_oats': 'oat' in text_lower,
        'crop_canola': 'canola' in text_lower or 'rapeseed' in text_lower,
        'crop_sunflower': 'sunflower' in text_lower,
        'crop_peanuts': 'peanut' in text_lower,
        'crop_sugar': any(keyword in text_lower for keyword in [
            'sugar beet', 'sugarbeet', 'sugar cane', 'sugarcane'
        ]),
        'crop_tobacco': 'tobacco' in text_lower,
        'crop_dry_beans': any(keyword in text_lower for keyword in [
            'dry bean', 'dry pea', 'lentil', 'chickpea', 'pulse'
        ]),

        # Specialty Crops (more specific)
        'specialty_crop_fruits': any(keyword in text_lower for keyword in [
            'apple', 'orange', 'grape', 'berry', 'cherry', 'peach', 'pear', 'plum', 'citrus', 'fruit tree'
        ]),
        'specialty_crop_vegetables': any(keyword in text_lower for keyword in [
            'tomato', 'potato', 'onion', 'lettuce', 'carrot', 'pepper', 'cabbage', 'cucumber', 'vegetable'
        ]),
        'specialty_crop_nuts': any(keyword in text_lower for keyword in [
            'almond', 'walnut', 'pecan', 'hazelnut', 'pistachio', 'nut tree'
        ]),
        'specialty_crop_nursery': any(keyword in text_lower for keyword in [
            'nursery', 'greenhouse', 'ornamental', 'floriculture', 'flower'
        ]),

        # Forage and Pasture
        'forage_hay': any(keyword in text_lower for keyword in [
            'hay', 'alfalfa', 'forage', 'pasture', 'grazing', 'rangeland', 'grassland'
        ]),

        # Forestry
        'forestry': any(keyword in text_lower for keyword in [
            'timber', 'forest', 'tree farm', 'woodland', 'silviculture'
        ]),

        # Commodities (grouped categories - kept for backwards compatibility)
        'commodity_grains': any(keyword in text_lower for keyword in [
            'wheat', 'corn', 'grain', 'barley', 'oat', 'sorghum'
        ]),
        'commodity_oilseeds': any(keyword in text_lower for keyword in [
            'soybean', 'canola', 'sunflower', 'flax'
        ]),
        'commodity_cotton': 'cotton' in text_lower,
        'commodity_rice': 'rice' in text_lower,
        'commodity_peanuts': 'peanut' in text_lower,
        'commodity_sugar': 'sugar' in text_lower,
        'commodity_tobacco': 'tobacco' in text_lower,

        # State-specific (North Dakota focus)
        'nd_specific': any(keyword in text_lower for keyword in [
            'north dakota', 'nd', 'northern plains'
        ]),
    }

    return criteria


def enhance_all_programs():
    """Re-process all programs with enhanced eligibility parsing"""

    db.connect()

    # Get all programs with eligibility text
    programs = db.fetch_all("""
        SELECT
            id,
            program_name,
            description,
            eligibility_raw,
            confidence_score
        FROM programs
        WHERE eligibility_raw IS NOT NULL
          AND confidence_score >= 0.5
        ORDER BY confidence_score DESC
    """)

    logger.info(f"Enhancing eligibility criteria for {len(programs)} programs...")

    updated = 0
    for program in programs:
        enhanced_criteria = extract_enhanced_criteria(
            program['eligibility_raw'],
            program['program_name'],
            program.get('description', '')
        )

        # Update the eligibility_parsed field
        db.update(
            'programs',
            {'eligibility_parsed': enhanced_criteria},
            'id = %s',
            (program['id'],)
        )

        updated += 1
        if updated % 10 == 0:
            logger.info(f"Processed {updated}/{len(programs)} programs...")

    logger.info(f"✓ Enhanced {updated} programs with detailed eligibility criteria")

    # Show sample results
    sample = db.fetch_one("""
        SELECT
            program_name,
            jsonb_pretty(eligibility_parsed) as criteria
        FROM programs
        WHERE content_type = 'program'
          AND eligibility_parsed IS NOT NULL
          AND jsonb_typeof(eligibility_parsed) = 'object'
        ORDER BY confidence_score DESC
        LIMIT 1
    """)

    if sample:
        logger.info(f"\nSample enhanced criteria for '{sample['program_name']}':")
        logger.info(sample['criteria'])

    db.close()


if __name__ == '__main__':
    enhance_all_programs()
