#!/usr/bin/env python3
"""
FSA Program Explorer - Web Interface
Browse and search farm programs from the database
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from src.database.connection import db
import logging
import re

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

logger = logging.getLogger(__name__)

# Lazy database connection - only connect when needed
def get_db():
    """Get database connection, connecting if not already connected"""
    if not db._connection:
        try:
            db.connect()
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    return db


def format_eligibility_text(eligibility_raw: str) -> dict:
    """
    Format raw eligibility text into structured, readable sections

    Returns:
        dict with 'intro', 'commodities', 'requirements', and 'formatted_html'
    """
    if not eligibility_raw:
        return {'intro': None, 'commodities': [], 'requirements': [], 'formatted_html': None}

    # Split by pipe separator and remove duplicates
    sections = eligibility_raw.split('|')
    unique_sections = []
    seen = set()

    for section in sections:
        section = section.strip()
        if section and section not in seen:
            unique_sections.append(section)
            seen.add(section)

    intro = None
    commodities = []
    requirements = []

    for section in unique_sections:
        # Check if this is a commodity list (contains multiple capital words stuck together)
        if 'include:' in section.lower() and re.search(r'[A-Z][a-z]+[A-Z][a-z]+', section):
            # Extract the list part
            parts = section.split('include:', 1)
            if len(parts) == 2:
                intro = parts[0].strip()
                commodity_text = parts[1].strip()

                # Split camelCase/PascalCase commodities
                # Handle multi-word items like "Dry peas", "Grain sorghum", etc.
                # First, add markers before capital letters (but not after spaces or opening parens)
                spaced = re.sub(r'([a-z\)])([A-Z])', r'\1||\2', commodity_text)
                # Split on the marker and clean up
                items = [item.strip() for item in spaced.split('||') if item.strip()]
                commodities = items

        # Check if this is a "Who Is Eligible" section
        elif 'who is eligible' in section.lower() or 'eligible applicants' in section.lower():
            # Extract just the requirements part
            text = re.sub(r'^.*?(?:Who Is Eligible|Eligible applicants)', '', section, flags=re.I).strip()
            if text and text not in requirements:
                requirements.append(text)

        # Otherwise it's an intro paragraph
        elif not intro and len(section) > 100 and 'include:' not in section.lower():
            # Take the part before "Eligible commodities" if present
            if 'eligible commodities' in section.lower():
                intro = section.split('Eligible commodities')[0].strip()
            else:
                intro = section

    return {
        'intro': intro,
        'commodities': commodities,
        'requirements': requirements
    }


# Register the filter for use in templates
app.jinja_env.filters['format_eligibility'] = format_eligibility_text


@app.route('/')
def index():
    """Home page with program statistics"""

    # Get summary stats (only actual programs, not rules/reports/etc)
    stats = {
        'total_programs': db.fetch_one("SELECT COUNT(*) as count FROM programs WHERE content_type = 'program'")['count'],
        'high_quality': db.fetch_one("SELECT COUNT(*) as count FROM programs WHERE content_type = 'program' AND confidence_score >= 0.7")['count'],
        'with_payment_info': db.fetch_one("SELECT COUNT(*) as count FROM programs WHERE content_type = 'program' AND payment_min IS NOT NULL")['count'],
        'with_eligibility': db.fetch_one("SELECT COUNT(*) as count FROM programs WHERE content_type = 'program' AND eligibility_raw IS NOT NULL")['count'],
    }

    # Get category breakdown (only actual programs)
    categories = db.fetch_all("""
        SELECT
          CASE
            WHEN program_name LIKE '%Loan%' THEN 'Loan Programs'
            WHEN program_name LIKE '%Conservation%' OR program_name LIKE '%CRP%' THEN 'Conservation'
            WHEN program_name LIKE '%Emergency%' OR program_name LIKE '%Disaster%' THEN 'Disaster/Emergency'
            WHEN program_name LIKE '%Marketing%' OR program_name LIKE '%Commodity%' THEN 'Marketing/Commodity'
            WHEN program_name LIKE '%Payment%' OR program_name LIKE '%Eligibility%' THEN 'Payment/Eligibility'
            ELSE 'Other'
          END as category,
          COUNT(*) as count
        FROM programs
        WHERE content_type = 'program' AND confidence_score >= 0.5
        GROUP BY category
        ORDER BY count DESC
    """)

    # Get featured high-quality programs
    featured_programs = db.fetch_all("""
        SELECT
          id,
          program_name,
          SUBSTRING(description FROM 1 FOR 150) as description_short,
          confidence_score,
          payment_min,
          payment_max,
          eligibility_parsed
        FROM programs
        WHERE content_type = 'program' AND confidence_score >= 0.8
          AND eligibility_parsed IS NOT NULL
          AND payment_min IS NOT NULL
        ORDER BY confidence_score DESC, program_name
        LIMIT 6
    """)

    return render_template('index.html', stats=stats, categories=categories, featured_programs=featured_programs)


@app.route('/programs')
def programs():
    """Program listing with filters"""

    # Get filter parameters
    category = request.args.get('category', '')
    min_confidence = float(request.args.get('min_confidence', 0.5))
    has_payment = request.args.get('has_payment', '')
    search = request.args.get('search', '')

    # Build query
    query = """
        SELECT
          id,
          program_name,
          SUBSTRING(description FROM 1 FOR 200) as description_short,
          confidence_score,
          payment_min,
          payment_max,
          payment_unit,
          CASE WHEN eligibility_raw IS NOT NULL THEN true ELSE false END as has_eligibility,
          source_url
        FROM programs
        WHERE content_type = 'program' AND confidence_score >= %s
    """
    params = [min_confidence]

    # Add filters
    if category and category != 'all':
        if category == 'Loan Programs':
            query += " AND program_name LIKE %s"
            params.append('%Loan%')
        elif category == 'Conservation':
            query += " AND (program_name LIKE %s OR program_name LIKE %s)"
            params.extend(['%Conservation%', '%CRP%'])
        elif category == 'Disaster/Emergency':
            query += " AND (program_name LIKE %s OR program_name LIKE %s)"
            params.extend(['%Emergency%', '%Disaster%'])

    if has_payment == 'yes':
        query += " AND payment_min IS NOT NULL"

    if search:
        query += " AND (program_name ILIKE %s OR description ILIKE %s)"
        search_term = f'%{search}%'
        params.extend([search_term, search_term])

    query += " ORDER BY confidence_score DESC, program_name LIMIT 100"

    programs = db.fetch_all(query, tuple(params))

    return render_template('programs.html',
                         programs=programs,
                         category=category,
                         min_confidence=min_confidence,
                         has_payment=has_payment,
                         search=search)


@app.route('/program/<int:program_id>')
def program_detail(program_id):
    """Program detail page"""

    program = db.fetch_one("""
        SELECT *
        FROM programs
        WHERE content_type = 'program' AND id = %s
    """, (program_id,))

    if not program:
        return "Program not found", 404

    return render_template('program_detail.html', program=program)


@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""

    # Category distribution
    categories = db.fetch_all("""
        SELECT
          CASE
            WHEN program_name LIKE '%Loan%' THEN 'Loan Programs'
            WHEN program_name LIKE '%Conservation%' OR program_name LIKE '%CRP%' THEN 'Conservation'
            WHEN program_name LIKE '%Emergency%' OR program_name LIKE '%Disaster%' THEN 'Disaster/Emergency'
            WHEN program_name LIKE '%Marketing%' OR program_name LIKE '%Commodity%' THEN 'Marketing/Commodity'
            ELSE 'Other'
          END as category,
          COUNT(*) as count,
          AVG(confidence_score) as avg_confidence
        FROM programs
        WHERE content_type = 'program' AND confidence_score >= 0.5
        GROUP BY category
        ORDER BY count DESC
    """)

    # Confidence distribution
    confidence_dist = db.fetch_all("""
        SELECT
          CASE
            WHEN confidence_score >= 0.9 THEN '0.9-1.0'
            WHEN confidence_score >= 0.7 THEN '0.7-0.9'
            WHEN confidence_score >= 0.5 THEN '0.5-0.7'
            ELSE '0.0-0.5'
          END as range,
          COUNT(*) as count
        FROM programs
        GROUP BY range
        ORDER BY MIN(confidence_score) DESC
    """)

    return jsonify({
        'categories': categories,
        'confidence_distribution': confidence_dist
    })


@app.route('/search')
def search():
    """Search endpoint"""
    query = request.args.get('q', '')

    if not query:
        return jsonify([])

    results = db.fetch_all("""
        SELECT
          id,
          program_name,
          SUBSTRING(description FROM 1 FOR 150) as description_short,
          confidence_score
        FROM programs
        WHERE content_type = 'program' AND program_name ILIKE %s
           OR description ILIKE %s
        ORDER BY confidence_score DESC
        LIMIT 20
    """, (f'%{query}%', f'%{query}%'))

    return jsonify(results)


@app.route('/finder')
def finder():
    """Program Finder - Match programs to farmer's situation"""

    # Get farmer's inputs from query params
    farm_type = request.args.getlist('farm_type')
    farmer_status = request.args.getlist('farmer_status')
    program_type = request.args.getlist('program_type')
    situation = request.args.getlist('situation')

    # Get farm profile inputs
    farm_profile = {
        'total_acres': request.args.get('total_acres', type=int),
        'gross_revenue': request.args.get('gross_revenue', type=float),
        'has_conservation_plan': request.args.get('conservation_plan'),
        'credit_status': request.args.get('credit_status'),
        'is_us_citizen': request.args.get('is_us_citizen'),
        'can_get_commercial_credit': request.args.get('commercial_credit'),
        'owns_farm': request.args.get('owns_farm'),
    }

    # Build matching criteria if form submitted
    matched_programs = []
    if any([farm_type, farmer_status, program_type, situation]):
        # Build WHERE clause for matching (use OR within categories, AND between categories)
        conditions = ["content_type = 'program'", "confidence_score >= 0.5", "eligibility_parsed IS NOT NULL"]

        # Farm Type matching (OR within this category)
        farm_type_conditions = []

        # Helper: check if program has NO specific crop flags (truly generic crop program)
        no_specific_crops = (
            "NOT COALESCE((eligibility_parsed->>'crop_wheat')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_corn')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_soybeans')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_cotton')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_rice')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_barley')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_sorghum')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_peanuts')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_sunflower')::boolean, false) AND "
            "NOT COALESCE((eligibility_parsed->>'crop_canola')::boolean, false)"
        )

        # Livestock types - match specific OR generic livestock
        if 'beef_cattle' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_beef_cattle')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'dairy_cattle' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_dairy_cattle')::boolean = true OR (eligibility_parsed->>'dairy')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'hogs' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_hogs')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'poultry' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_poultry')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'sheep_goats' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_sheep_goats')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'bees' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_bees')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")
        if 'aquaculture' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'livestock_aquaculture')::boolean = true OR ((eligibility_parsed->>'livestock')::boolean = true))")

        # Crop types - match specific OR truly generic (crop_farming with NO specific crops)
        if 'wheat' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_wheat')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'corn' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_corn')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'soybeans' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_soybeans')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'cotton' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_cotton')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'rice' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_rice')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'barley' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_barley')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'sorghum' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_sorghum')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'peanuts' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_peanuts')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'sunflower' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_sunflower')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")
        if 'canola' in farm_type:
            farm_type_conditions.append(f"((eligibility_parsed->>'crop_canola')::boolean = true OR ((eligibility_parsed->>'crop_farming')::boolean = true AND {no_specific_crops}))")

        # Specialty crops
        if 'fruits' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'specialty_crop_fruits')::boolean = true OR (eligibility_parsed->>'specialty_crops')::boolean = true)")
        if 'vegetables' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'specialty_crop_vegetables')::boolean = true OR (eligibility_parsed->>'specialty_crops')::boolean = true)")
        if 'nuts' in farm_type:
            farm_type_conditions.append("((eligibility_parsed->>'specialty_crop_nuts')::boolean = true OR (eligibility_parsed->>'specialty_crops')::boolean = true)")

        # Other types
        if 'hay_forage' in farm_type:
            farm_type_conditions.append("(eligibility_parsed->>'forage_hay')::boolean = true")
        if 'organic' in farm_type:
            farm_type_conditions.append("(eligibility_parsed->>'organic')::boolean = true")

        if farm_type_conditions:
            conditions.append("(" + " OR ".join(farm_type_conditions) + ")")

        # Farmer Status matching (OPTIONAL - used for ranking, not filtering)
        # Most programs don't explicitly mention farmer status in eligibility
        # So we don't filter by this - instead we'll boost ranking later
        farmer_status_conditions = []
        if 'beginning' in farmer_status:
            farmer_status_conditions.append("(eligibility_parsed->>'beginning_farmer')::boolean = true")
        if 'young' in farmer_status:
            farmer_status_conditions.append("(eligibility_parsed->>'young_farmer')::boolean = true")
        if 'veteran' in farmer_status:
            farmer_status_conditions.append("(eligibility_parsed->>'veteran')::boolean = true")
        # NOTE: Not adding to conditions - farmer status is informational only

        # Program Type matching (OR within this category)
        program_type_conditions = []
        if 'loans' in program_type:
            program_type_conditions.append("(eligibility_parsed->>'is_loan')::boolean = true")
        if 'payments' in program_type:
            program_type_conditions.append("(eligibility_parsed->>'is_payment')::boolean = true")
        if 'insurance' in program_type:
            program_type_conditions.append("(eligibility_parsed->>'is_insurance')::boolean = true")
        if 'conservation' in program_type:
            program_type_conditions.append("(eligibility_parsed->>'is_conservation')::boolean = true")
        if program_type_conditions:
            conditions.append("(" + " OR ".join(program_type_conditions) + ")")

        # Situation matching (OPTIONAL - used for ranking, not filtering)
        # Many general programs can help with these situations even if not specifically designed for them
        situation_conditions = []
        if 'disaster' in situation:
            situation_conditions.append("(eligibility_parsed->>'is_disaster')::boolean = true")
        if 'price_loss' in situation:
            situation_conditions.append("(eligibility_parsed->>'for_price_loss')::boolean = true")
        if 'need_equipment' in situation:
            situation_conditions.append("(eligibility_parsed->>'for_equipment')::boolean = true")
        if 'buy_land' in situation:
            situation_conditions.append("(eligibility_parsed->>'for_land_purchase')::boolean = true")
        # NOTE: Not adding to conditions - situation is informational only

        # Execute query (AND between categories)
        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT
              id,
              program_name,
              SUBSTRING(description FROM 1 FOR 200) as description_short,
              confidence_score,
              payment_min,
              payment_max,
              payment_unit,
              source_url,
              eligibility_parsed,
              ai_summary,
              eligibility_requirements
            FROM programs
            WHERE {where_clause}
            ORDER BY confidence_score DESC, program_name
            LIMIT 50
        """

        matched_programs = db.fetch_all(query)

        # Calculate match scores for each program
        for program in matched_programs:
            criteria = program.get('eligibility_parsed', {})
            match_count = 0
            # Don't count farmer_status or situation in total since they're optional
            total_criteria = len(farm_type) + len(program_type)
            # But we'll add bonus points for farmer status and situation matches

            # Count how many selected criteria match
            # Livestock types
            if 'beef_cattle' in farm_type and (criteria.get('livestock_beef_cattle') or criteria.get('livestock')):
                match_count += 1
            if 'dairy_cattle' in farm_type and (criteria.get('livestock_dairy_cattle') or criteria.get('dairy') or criteria.get('livestock')):
                match_count += 1
            if 'hogs' in farm_type and (criteria.get('livestock_hogs') or criteria.get('livestock')):
                match_count += 1
            if 'poultry' in farm_type and (criteria.get('livestock_poultry') or criteria.get('livestock')):
                match_count += 1
            if 'sheep_goats' in farm_type and (criteria.get('livestock_sheep_goats') or criteria.get('livestock')):
                match_count += 1
            if 'bees' in farm_type and (criteria.get('livestock_bees') or criteria.get('livestock')):
                match_count += 1
            if 'aquaculture' in farm_type and (criteria.get('livestock_aquaculture') or criteria.get('livestock')):
                match_count += 1

            # Crop types - only match generic if NO specific crops are set
            has_no_specific_crops = not any([
                criteria.get('crop_wheat'), criteria.get('crop_corn'), criteria.get('crop_soybeans'),
                criteria.get('crop_cotton'), criteria.get('crop_rice'), criteria.get('crop_barley'),
                criteria.get('crop_sorghum'), criteria.get('crop_peanuts'), criteria.get('crop_sunflower'),
                criteria.get('crop_canola')
            ])

            if 'wheat' in farm_type and (criteria.get('crop_wheat') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'corn' in farm_type and (criteria.get('crop_corn') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'soybeans' in farm_type and (criteria.get('crop_soybeans') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'cotton' in farm_type and (criteria.get('crop_cotton') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'rice' in farm_type and (criteria.get('crop_rice') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'barley' in farm_type and (criteria.get('crop_barley') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'sorghum' in farm_type and (criteria.get('crop_sorghum') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'peanuts' in farm_type and (criteria.get('crop_peanuts') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'sunflower' in farm_type and (criteria.get('crop_sunflower') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1
            if 'canola' in farm_type and (criteria.get('crop_canola') or (criteria.get('crop_farming') and has_no_specific_crops)):
                match_count += 1

            # Specialty crops
            if 'fruits' in farm_type and (criteria.get('specialty_crop_fruits') or criteria.get('specialty_crops')):
                match_count += 1
            if 'vegetables' in farm_type and (criteria.get('specialty_crop_vegetables') or criteria.get('specialty_crops')):
                match_count += 1
            if 'nuts' in farm_type and (criteria.get('specialty_crop_nuts') or criteria.get('specialty_crops')):
                match_count += 1

            # Other types
            if 'hay_forage' in farm_type and criteria.get('forage_hay'):
                match_count += 1
            if 'organic' in farm_type and criteria.get('organic'):
                match_count += 1
            if 'beginning' in farmer_status and criteria.get('beginning_farmer'):
                match_count += 1
            if 'young' in farmer_status and criteria.get('young_farmer'):
                match_count += 1
            if 'veteran' in farmer_status and criteria.get('veteran'):
                match_count += 1
            if 'loans' in program_type and criteria.get('is_loan'):
                match_count += 1
            if 'payments' in program_type and criteria.get('is_payment'):
                match_count += 1
            if 'insurance' in program_type and criteria.get('is_insurance'):
                match_count += 1
            if 'conservation' in program_type and criteria.get('is_conservation'):
                match_count += 1
            if 'disaster' in situation and criteria.get('is_disaster'):
                match_count += 1
            if 'price_loss' in situation and criteria.get('for_price_loss'):
                match_count += 1
            if 'need_equipment' in situation and criteria.get('for_equipment'):
                match_count += 1
            if 'buy_land' in situation and criteria.get('for_land_purchase'):
                match_count += 1

            # Calculate base match score from required criteria
            base_score = round((match_count / total_criteria * 100) if total_criteria > 0 else 0)

            # Add bonus points for farmer status and situation matches (up to +25%)
            bonus_points = 0
            if 'beginning' in farmer_status and criteria.get('beginning_farmer'):
                bonus_points += 5
            if 'young' in farmer_status and criteria.get('young_farmer'):
                bonus_points += 5
            if 'veteran' in farmer_status and criteria.get('veteran'):
                bonus_points += 5
            if 'disaster' in situation and criteria.get('is_disaster'):
                bonus_points += 5
            if 'price_loss' in situation and criteria.get('for_price_loss'):
                bonus_points += 5
            if 'need_equipment' in situation and criteria.get('for_equipment'):
                bonus_points += 5
            if 'buy_land' in situation and criteria.get('for_land_purchase'):
                bonus_points += 5

            program['match_score'] = min(100, base_score + bonus_points)
            program['has_bonus_match'] = bonus_points > 0

            # Generate "Why This Matches" explanation
            matches = []

            # Farm type matches
            if 'beef_cattle' in farm_type and criteria.get('livestock_beef_cattle'):
                matches.append('Supports beef cattle operations')
            if 'dairy_cattle' in farm_type and criteria.get('livestock_dairy_cattle'):
                matches.append('Designed for dairy operations')
            if 'hogs' in farm_type and criteria.get('livestock_hogs'):
                matches.append('Available for hog producers')
            if 'poultry' in farm_type and criteria.get('livestock_poultry'):
                matches.append('Serves poultry farms')
            if 'sheep_goats' in farm_type and criteria.get('livestock_sheep_goats'):
                matches.append('Open to sheep and goat operations')
            if 'bees' in farm_type and criteria.get('livestock_bees'):
                matches.append('Supports beekeepers and honey producers')
            if 'aquaculture' in farm_type and criteria.get('livestock_aquaculture'):
                matches.append('Available for aquaculture operations')

            if 'wheat' in farm_type and criteria.get('crop_wheat'):
                matches.append('Covers wheat production')
            if 'corn' in farm_type and criteria.get('crop_corn'):
                matches.append('Includes corn crops')
            if 'soybeans' in farm_type and criteria.get('crop_soybeans'):
                matches.append('Applies to soybean farmers')
            if 'cotton' in farm_type and criteria.get('crop_cotton'):
                matches.append('Available for cotton growers')
            if 'rice' in farm_type and criteria.get('crop_rice'):
                matches.append('Covers rice production')
            if 'barley' in farm_type and criteria.get('crop_barley'):
                matches.append('Includes barley crops')
            if 'sorghum' in farm_type and criteria.get('crop_sorghum'):
                matches.append('Applies to sorghum/milo farmers')
            if 'peanuts' in farm_type and criteria.get('crop_peanuts'):
                matches.append('Available for peanut growers')
            if 'sunflower' in farm_type and criteria.get('crop_sunflower'):
                matches.append('Covers sunflower production')
            if 'canola' in farm_type and criteria.get('crop_canola'):
                matches.append('Includes canola/rapeseed')

            if 'fruits' in farm_type and criteria.get('specialty_crop_fruits'):
                matches.append('Supports fruit growers')
            if 'vegetables' in farm_type and criteria.get('specialty_crop_vegetables'):
                matches.append('Available for vegetable farmers')
            if 'nuts' in farm_type and criteria.get('specialty_crop_nuts'):
                matches.append('Covers nut tree operations')
            if 'hay_forage' in farm_type and criteria.get('forage_hay'):
                matches.append('Includes hay and forage producers')
            if 'organic' in farm_type and criteria.get('organic'):
                matches.append('Available for organic farmers')

            # Program type matches
            if 'loans' in program_type and criteria.get('is_loan'):
                matches.append('Provides loan financing')
            if 'payments' in program_type and criteria.get('is_payment'):
                matches.append('Offers direct payments')
            if 'insurance' in program_type and criteria.get('is_insurance'):
                matches.append('Risk management/insurance program')
            if 'conservation' in program_type and criteria.get('is_conservation'):
                matches.append('Conservation-focused program')

            # Farmer status matches (bonus)
            if 'beginning' in farmer_status and criteria.get('beginning_farmer'):
                matches.append('Prioritizes beginning farmers')
            if 'young' in farmer_status and criteria.get('young_farmer'):
                matches.append('Supports young farmers')
            if 'veteran' in farmer_status and criteria.get('veteran'):
                matches.append('Serves veteran farmers')

            # Situation matches (bonus)
            if 'disaster' in situation and criteria.get('is_disaster'):
                matches.append('Provides disaster assistance')
            if 'price_loss' in situation and criteria.get('for_price_loss'):
                matches.append('Helps with price/market losses')
            if 'need_equipment' in situation and criteria.get('for_equipment'):
                matches.append('Can fund equipment purchases')
            if 'buy_land' in situation and criteria.get('for_land_purchase'):
                matches.append('Helps with land acquisition')

            program['why_matches'] = matches

            # Check eligibility requirements
            if program.get('eligibility_requirements'):
                requirements = program['eligibility_requirements'].get('requirements', [])
                met = []
                not_met = []
                unknown = []

                for req in requirements:
                    req_key = req['key']
                    status = 'unknown'  # default

                    # Check each requirement against farm profile
                    if req_key == 'is_us_citizen' and farm_profile['is_us_citizen']:
                        status = 'met' if farm_profile['is_us_citizen'] == 'yes' else 'not_met' if farm_profile['is_us_citizen'] == 'no' else 'unknown'
                    elif req_key == 'has_conservation_plan' and farm_profile['has_conservation_plan']:
                        status = 'met' if farm_profile['has_conservation_plan'] == 'yes' else 'not_met' if farm_profile['has_conservation_plan'] == 'no' else 'unknown'
                    elif req_key == 'has_satisfactory_credit' and farm_profile['credit_status']:
                        status = 'met' if farm_profile['credit_status'] == 'good' else 'not_met' if farm_profile['credit_status'] == 'poor' else 'unknown'
                    elif req_key == 'cannot_get_commercial_credit' and farm_profile['can_get_commercial_credit']:
                        status = 'met' if farm_profile['can_get_commercial_credit'] == 'no' else 'not_met' if farm_profile['can_get_commercial_credit'] == 'yes' else 'unknown'
                    elif req_key == 'is_beginning_farmer':
                        status = 'met' if 'beginning' in farmer_status else 'unknown'
                    elif req_key == 'is_veteran':
                        status = 'met' if 'veteran' in farmer_status else 'unknown'
                    elif req_key == 'is_socially_disadvantaged':
                        # We don't collect this in the form yet, so it's always unknown
                        status = 'unknown'
                    elif req_key == 'meets_agi_limit' and farm_profile['gross_revenue']:
                        # Typical AGI limit is $900,000
                        status = 'met' if farm_profile['gross_revenue'] < 900000 else 'not_met'
                    elif req_key == 'is_farm_owner' or req_key == 'owns_and_operates_farm':
                        status = 'met' if farm_profile['owns_farm'] == 'yes' else 'not_met' if farm_profile['owns_farm'] == 'no' else 'unknown'
                    elif req_key == 'operates_farm':
                        # Assume they operate if they're using the finder
                        status = 'met'

                    req_with_status = {**req, 'status': status}
                    if status == 'met':
                        met.append(req_with_status)
                    elif status == 'not_met':
                        not_met.append(req_with_status)
                    else:
                        unknown.append(req_with_status)

                program['eligibility_check'] = {
                    'met': met,
                    'not_met': not_met,
                    'unknown': unknown,
                    'total': len(requirements),
                    'met_count': len(met),
                    'not_met_count': len(not_met),
                    'unknown_count': len(unknown),
                    'score': round(len(met) / len(requirements) * 100) if requirements else 0
                }

        # Sort by match score
        matched_programs.sort(key=lambda x: x['match_score'], reverse=True)

    return render_template('finder.html',
                         matched_programs=matched_programs,
                         farm_type=farm_type,
                         farmer_status=farmer_status,
                         program_type=program_type,
                         situation=situation,
                         farm_profile=farm_profile)


@app.route('/my-programs')
def my_programs():
    """Display user's selected programs with next steps and payment estimates"""

    # Get program IDs from query string (will be sent by JavaScript from localStorage)
    program_ids = request.args.get('ids', '')

    if not program_ids:
        # No programs selected yet
        return render_template('my_programs.html', programs=[])

    # Parse comma-separated IDs
    id_list = [int(id.strip()) for id in program_ids.split(',') if id.strip().isdigit()]

    if not id_list:
        return render_template('my_programs.html', programs=[])

    # Fetch full program details for selected programs
    placeholders = ','.join(['%s'] * len(id_list))
    query = f"""
        SELECT
            id,
            program_name,
            description,
            eligibility_raw,
            eligibility_requirements,
            payment_min,
            payment_max,
            payment_unit,
            payment_info_raw,
            source_url,
            ai_summary,
            confidence_score
        FROM programs
        WHERE id IN ({placeholders})
        ORDER BY program_name
    """

    programs = db.fetch_all(query, tuple(id_list))

    return render_template('my_programs.html', programs=programs)


@app.route('/health')
def health_check():
    """Health check endpoint for load balancers and monitoring"""
    try:
        # Test database connection
        db.fetch_one("SELECT 1")
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


if __name__ == '__main__':
    app.run(debug=True, port=5001)
