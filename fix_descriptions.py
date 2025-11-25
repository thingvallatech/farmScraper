#!/usr/bin/env python3
"""
Fix Description Data Quality
Re-extracts program descriptions from raw_text, skipping header boilerplate
"""
import re
from src.database.connection import db
from bs4 import BeautifulSoup

def clean_text(text: str) -> str:
    """Remove extra whitespace and normalize text"""
    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_better_description(raw_html: str, raw_text: str, program_name: str) -> str:
    """
    Extract a better description by:
    1. Skipping header/navigation boilerplate
    2. Finding the main content area
    3. Extracting the first meaningful paragraph
    """
    soup = BeautifulSoup(raw_html, 'html.parser')

    # Strategy 1: Look for sections with "What It Is" or similar headings
    what_it_is_section = soup.find(['h2', 'h3', 'h4'], text=re.compile(r'What It Is|Overview|Description|About', re.I))
    if what_it_is_section:
        # Get the next paragraph(s) after this heading
        next_elem = what_it_is_section.find_next(['p', 'div'])
        if next_elem:
            desc_text = next_elem.get_text(strip=True)
            if len(desc_text) > 100 and 'Official websites' not in desc_text:
                return clean_text(desc_text)[:500]  # Limit to 500 chars

    # Strategy 2: Look for main content area by class/id
    main_content = soup.find(['main', 'article', 'div'], {'class': re.compile(r'content|main|body', re.I)})
    if main_content:
        # Find first substantial paragraph in main content
        paragraphs = main_content.find_all('p')
        for p in paragraphs[:10]:
            text = p.get_text(strip=True)
            # Skip if it's boilerplate
            if len(text) > 100 and not any(skip in text for skip in [
                'Official websites',
                'Here\'s how you know',
                'Skip to main content',
                'An official website',
                '.gov',
                'Breadcrumb',
                'About FSA',
                'Apply for a Loan',
                'Contact Us'
            ]):
                return clean_text(text)[:500]

    # Strategy 3: Parse raw_text and skip header content
    if raw_text:
        # Split by common section markers
        sections = re.split(r'(?:What It Is|Overview|Description|Program Details)', raw_text, flags=re.I)
        if len(sections) > 1:
            # Get the section after "What It Is"
            content = sections[1]
            # Get first paragraph (split by double newline or period)
            paragraphs = re.split(r'\n\n+|\. {2,}', content)
            for p in paragraphs[:5]:
                p = clean_text(p)
                if len(p) > 100 and not any(skip in p for skip in [
                    'Official websites',
                    'Here\'s how you know',
                    'Skip to main content',
                    'An official website'
                ]):
                    return p[:500]

    # Strategy 4: Look for text that follows the program name
    if program_name and raw_text:
        # Find where program name appears in text
        name_match = re.search(re.escape(program_name), raw_text, re.I)
        if name_match:
            # Get text after the program name
            after_name = raw_text[name_match.end():name_match.end() + 1000]
            # Clean and extract first sentence/paragraph
            sentences = re.split(r'\.\s+', after_name)
            for sentence in sentences[:3]:
                sentence = clean_text(sentence)
                if len(sentence) > 100:
                    return sentence[:500]

    # Fallback: return None (no good description found)
    return None

def main():
    """Fix all program descriptions"""
    db.connect()

    print("Fetching programs with bad descriptions...")

    # Get all programs that have the boilerplate description
    programs = db.fetch_all("""
        SELECT p.id, p.program_name, p.description, p.source_url, rp.raw_html, rp.raw_text
        FROM programs p
        LEFT JOIN raw_pages rp ON p.source_url = rp.url
        WHERE p.description LIKE '%Official websites%'
           OR p.description LIKE '%An official website%'
           OR p.description IS NULL
           OR LENGTH(p.description) < 50
        ORDER BY p.confidence_score DESC
    """)

    print(f"Found {len(programs)} programs with bad descriptions")

    fixed_count = 0
    skipped_count = 0

    for program in programs:
        program_id = program['id']
        program_name = program['program_name']
        old_desc = program['description']
        raw_html = program['raw_html']
        raw_text = program['raw_text']

        if not raw_html and not raw_text:
            print(f"  ⚠️  Skipping {program_name} - no raw data")
            skipped_count += 1
            continue

        # Extract better description
        new_desc = extract_better_description(raw_html, raw_text, program_name)

        if new_desc and new_desc != old_desc:
            # Update database
            db.execute(
                "UPDATE programs SET description = %s WHERE id = %s",
                (new_desc, program_id)
            )
            print(f"  ✓ Fixed: {program_name}")
            print(f"    Old: {old_desc[:80] if old_desc else 'None'}...")
            print(f"    New: {new_desc[:80]}...")
            fixed_count += 1
        else:
            print(f"  ⚠️  No improvement: {program_name}")
            skipped_count += 1

    db.close()

    print(f"\n{'='*60}")
    print(f"Description Fix Complete:")
    print(f"  Fixed: {fixed_count} programs")
    print(f"  Skipped: {skipped_count} programs")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
