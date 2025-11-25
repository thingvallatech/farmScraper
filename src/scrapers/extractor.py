"""
Program Data Extractor
Extracts structured information from HTML pages using patterns and NLP
"""
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.database.connection import db

logger = logging.getLogger(__name__)

# Initialize spacy if available
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    NLP_AVAILABLE = True
except (ImportError, OSError):
    logger.warning("Spacy not available - NLP features disabled")
    NLP_AVAILABLE = False
    nlp = None


class ProgramExtractor:
    """Extract structured program data from HTML content"""

    # Payment patterns
    PAYMENT_PATTERNS = [
        r'\$[\d,]+\.?\d*\s*(?:per|/)\s*acre',
        r'\$[\d,]+\.?\d*\s*(?:per|/)\s*head',
        r'\$[\d,]+\.?\d*\s*(?:per|/)\s*bushel',
        r'(?:up to|maximum of?)\s*\$[\d,]+\.?\d*',
        r'[\d,]+\.?\d*%\s*of\s*(?:losses|costs|expenses|value)',
        r'payment rate[s]?\s*(?:is|are|of)?\s*\$[\d,]+\.?\d*',
        r'\$[\d,]+\.?\d*\s*to\s*\$[\d,]+\.?\d*',
        r'between\s*\$[\d,]+\.?\d*\s*and\s*\$[\d,]+\.?\d*',
    ]

    # Deadline patterns
    DEADLINE_PATTERNS = [
        r'(?:deadline|due date|apply by|submit by)[:\s]+([A-Z][a-z]+ \d{1,2},?\s*\d{4})',
        r'(?:applications? (?:open|close)[s]?)[:\s]+([A-Z][a-z]+ \d{1,2},?\s*\d{4})',
        r'(?:enrollment period)[:\s]+([A-Z][a-z]+ \d{1,2}.*?through.*?\d{4})',
        r'(?:sign.?up|signup) (?:begins|starts|ends)[:\s]+([A-Z][a-z]+ \d{1,2},?\s*\d{4})',
    ]

    def __init__(self):
        self.extracted_count = 0

    def extract_program_data(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract structured program information from HTML

        Args:
            html_content: HTML content of page
            url: Source URL

        Returns:
            Dictionary of extracted program data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()

        program_data = {
            'source_url': url,
            'program_name': self.extract_program_name(soup, url),
            'program_code': self.extract_program_code(soup, text),
            'description': self.extract_description(soup),
            'eligibility_raw': self.extract_eligibility(soup),
            'eligibility_parsed': self.parse_eligibility(soup),
            'payment_info_raw': None,
            'payment_formula': None,
            'payment_min': None,
            'payment_max': None,
            'payment_unit': None,
            'payment_range_text': None,
            'application_start': None,
            'application_end': None,
            'deadline_text': None,
            'confidence_score': 0.0,
            'extraction_warnings': []
        }

        # Extract payment information
        payment_info = self.extract_payment_info(soup, text)
        program_data.update(payment_info)

        # Extract deadlines
        deadline_info = self.extract_deadlines(soup, text)
        program_data.update(deadline_info)

        # Calculate confidence score
        program_data['confidence_score'] = self.calculate_confidence(program_data)

        return program_data

    def extract_program_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract program name from page"""
        # Try h1, h2, title
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        title = soup.find('title')
        if title:
            title_text = title.get_text(strip=True)
            # Remove common suffixes
            title_text = re.sub(r'\s*\|\s*.*$', '', title_text)
            return title_text

        # Fallback to URL
        path = url.split('/')[-1]
        return path.replace('-', ' ').replace('.html', '').title()

    def extract_program_code(self, soup: BeautifulSoup, text: str) -> Optional[str]:
        """Extract program code/abbreviation"""
        # Common program codes
        code_pattern = r'\b([A-Z]{2,6})\b'

        # Look for acronyms in parentheses
        paren_pattern = r'\(([A-Z]{2,6})\)'
        matches = re.findall(paren_pattern, text)

        if matches:
            return matches[0]

        # Look for program codes near "program" keyword
        program_sections = re.split(r'(?i)program', text)[:2]
        for section in program_sections:
            matches = re.findall(code_pattern, section[:200])
            if matches:
                # Filter out common false positives
                filtered = [m for m in matches if m not in ['FSA', 'USDA', 'USA', 'PDF']]
                if filtered:
                    return filtered[0]

        return None

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract program description"""
        # Look for meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']

        # Look for first substantial paragraph
        paragraphs = soup.find_all('p')
        for p in paragraphs[:5]:
            text = p.get_text(strip=True)
            if len(text) > 100:  # Substantial content
                return text

        return None

    def extract_eligibility(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract raw eligibility text"""
        # Find sections with eligibility keywords
        eligibility_sections = soup.find_all(
            ['div', 'section', 'p', 'li'],
            text=re.compile(r'eligib', re.I)
        )

        eligibility_texts = []

        for section in eligibility_sections[:5]:
            # Get parent context
            parent = section.parent if section.parent else section
            text = parent.get_text(strip=True)

            if 50 < len(text) < 1000:  # Reasonable length
                eligibility_texts.append(text)

        return ' | '.join(eligibility_texts) if eligibility_texts else None

    def parse_eligibility(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Parse eligibility into structured format"""
        eligibility_raw = self.extract_eligibility(soup)

        if not eligibility_raw:
            return None

        # Simple parsing - can be enhanced
        parsed = {
            'requires_farm_ownership': bool(re.search(r'own|ownership|operator', eligibility_raw, re.I)),
            'requires_acreage': bool(re.search(r'acre|land|farm size', eligibility_raw, re.I)),
            'income_limits': bool(re.search(r'income|agi|adjusted gross', eligibility_raw, re.I)),
            'conservation_requirements': bool(re.search(r'conservation|environmental', eligibility_raw, re.I)),
        }

        return parsed

    def extract_payment_info(self, soup: BeautifulSoup, text: str) -> Dict:
        """Extract payment rate information"""
        result = {
            'payment_info_raw': None,
            'payment_min': None,
            'payment_max': None,
            'payment_unit': None,
            'payment_range_text': None,
        }

        all_matches = []

        # Apply all payment patterns
        for pattern in self.PAYMENT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            all_matches.extend(matches)

        if all_matches:
            result['payment_info_raw'] = ' | '.join(all_matches)
            result['payment_range_text'] = all_matches[0] if all_matches else None

            # Extract numeric values
            amounts = self._extract_amounts(all_matches)
            if amounts:
                result['payment_min'] = min(amounts)
                result['payment_max'] = max(amounts)

            # Extract unit
            result['payment_unit'] = self._extract_payment_unit(all_matches)

        return result

    def _extract_amounts(self, payment_strings: List[str]) -> List[float]:
        """Extract numeric amounts from payment strings"""
        amounts = []

        for s in payment_strings:
            # Find all dollar amounts
            dollar_pattern = r'\$[\d,]+\.?\d*'
            matches = re.findall(dollar_pattern, s)

            for match in matches:
                try:
                    amount = float(match.replace('$', '').replace(',', ''))
                    amounts.append(amount)
                except ValueError:
                    continue

        return amounts

    def _extract_payment_unit(self, payment_strings: List[str]) -> Optional[str]:
        """Determine payment unit (per acre, per head, etc.)"""
        combined = ' '.join(payment_strings).lower()

        units = ['acre', 'head', 'bushel', 'cwt', 'ton', 'animal']

        for unit in units:
            if unit in combined:
                return f"per {unit}"

        if '%' in combined:
            return 'percentage'

        return 'flat_rate'

    def extract_deadlines(self, soup: BeautifulSoup, text: str) -> Dict:
        """Extract deadline information"""
        result = {
            'application_start': None,
            'application_end': None,
            'deadline_text': None,
        }

        deadlines = []

        for pattern in self.DEADLINE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            deadlines.extend(matches)

        if deadlines:
            result['deadline_text'] = ' | '.join(deadlines)

            # Try to parse dates
            parsed_dates = []
            for deadline_str in deadlines:
                try:
                    date = date_parser.parse(deadline_str, fuzzy=True)
                    parsed_dates.append(date)
                except (ValueError, TypeError):
                    continue

            if parsed_dates:
                parsed_dates.sort()
                result['application_start'] = parsed_dates[0].date() if len(parsed_dates) > 1 else None
                result['application_end'] = parsed_dates[-1].date()

        return result

    def calculate_confidence(self, program_data: Dict) -> float:
        """
        Calculate confidence score for extraction

        Score based on completeness and quality of extracted data
        """
        score = 0.0

        # Program name (required)
        if program_data.get('program_name'):
            score += 0.2

        # Description
        if program_data.get('description') and len(program_data['description']) > 50:
            score += 0.2

        # Payment information
        if program_data.get('payment_min') or program_data.get('payment_info_raw'):
            score += 0.3

        # Eligibility
        if program_data.get('eligibility_raw'):
            score += 0.2

        # Deadlines
        if program_data.get('application_end') or program_data.get('deadline_text'):
            score += 0.1

        return min(score, 1.0)


async def process_discovered_pages():
    """Process all discovered program pages and extract data"""
    logger.info("Starting program data extraction...")

    # Get all pages with program-related URLs from database
    # Process all pages that likely contain program information
    query = """
        SELECT id, url, raw_html, raw_text
        FROM raw_pages
        WHERE url LIKE '%program%'
           OR url LIKE '%assistance%'
           OR url LIKE '%loan%'
           OR url LIKE '%insurance%'
           OR url LIKE '%conservation%'
           OR url LIKE '%disaster%'
           OR url LIKE '%payment%'
           OR url LIKE '%subsidy%'
        ORDER BY url
    """

    pages = db.fetch_all(query)
    logger.info(f"Found {len(pages)} program pages to process")

    extractor = ProgramExtractor()

    for page in pages:
        try:
            program_data = extractor.extract_program_data(
                html_content=page['raw_html'],
                url=page['url']
            )

            # Save to database
            db.upsert_program(**program_data)
            extractor.extracted_count += 1

            logger.info(
                f"Extracted program: {program_data['program_name']} "
                f"(confidence: {program_data['confidence_score']:.2f})"
            )

        except Exception as e:
            logger.error(f"Error extracting from {page['url']}: {e}")

    logger.info(f"Extraction complete: {extractor.extracted_count} programs processed")


if __name__ == "__main__":
    # For testing
    import asyncio
    asyncio.run(process_discovered_pages())
