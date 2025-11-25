"""
Tier 1 API Scrapers - Structured data sources
Handles NASS QuickStats API and EWG subsidy database
"""
import asyncio
import logging
from typing import Dict, List, Optional
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from psycopg2.extras import Json

from src.config import settings
from src.database.connection import db

logger = logging.getLogger(__name__)


class NASSQuickStatsAPI:
    """NASS QuickStats API client"""

    BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.nass_api_key
        if not self.api_key:
            logger.warning("NASS API key not provided - API calls will fail")

    async def fetch_county_data(
        self,
        state: str,
        year_start: int = 2018,
        year_end: int = 2023,
        commodities: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Fetch county-level agricultural data from NASS QuickStats

        Args:
            state: State abbreviation (e.g., 'ND')
            year_start: Starting year
            year_end: Ending year
            commodities: List of commodities to fetch (None = all major crops)

        Returns:
            List of data records
        """
        if commodities is None:
            commodities = ['CORN', 'SOYBEANS', 'WHEAT', 'BARLEY', 'SUNFLOWER']

        all_data = []

        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            for commodity in commodities:
                for year in range(year_start, year_end + 1):
                    try:
                        params = {
                            'key': self.api_key,
                            'source_desc': 'SURVEY',
                            'sector_desc': 'CROPS',
                            'commodity_desc': commodity,
                            'state_alpha': state,
                            'year': year,
                            'agg_level_desc': 'COUNTY',
                            'format': 'JSON'
                        }

                        logger.info(f"Fetching NASS data: {commodity} {year} {state}")
                        response = await client.get(self.BASE_URL, params=params)
                        response.raise_for_status()

                        data = response.json()
                        if 'data' in data:
                            all_data.extend(data['data'])
                            logger.info(f"Retrieved {len(data['data'])} records for {commodity} {year}")

                        # Respectful delay
                        await asyncio.sleep(settings.scrape_delay_seconds)

                    except httpx.HTTPError as e:
                        logger.error(f"Error fetching NASS data for {commodity} {year}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error: {e}")

        return all_data

    async def save_to_database(self, data: List[Dict]) -> int:
        """Save NASS data to database"""
        saved_count = 0

        for record in data:
            try:
                query = """
                    INSERT INTO nass_data (
                        state, county, year, commodity, data_item,
                        value, unit, source_desc, raw_response
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (state, county, year, commodity, data_item) DO UPDATE
                    SET value = EXCLUDED.value,
                        unit = EXCLUDED.unit,
                        fetched_at = NOW()
                """

                params = (
                    record.get('state_alpha'),
                    record.get('county_name'),
                    int(record.get('year', 0)),
                    record.get('commodity_desc'),
                    record.get('short_desc'),
                    float(record.get('Value', 0)) if record.get('Value') else None,
                    record.get('unit_desc'),
                    record.get('source_desc'),
                    Json(record)
                )

                with db.get_cursor() as cursor:
                    cursor.execute(query, params)
                    saved_count += 1

            except Exception as e:
                logger.error(f"Error saving NASS record: {e}")

        logger.info(f"Saved {saved_count} NASS records to database")
        return saved_count


class EWGSubsidyDatabase:
    """EWG Farm Subsidy Database scraper"""

    BASE_URL = "https://farm.ewg.org"
    SEARCH_URL = f"{BASE_URL}/search.php"

    async def fetch_state_data(
        self,
        state: str = "ND",
        year_start: int = 2018,
        year_end: int = 2023
    ) -> List[Dict]:
        """
        Scrape EWG subsidy database for state-level payment data

        Args:
            state: State abbreviation
            year_start: Starting year
            year_end: Ending year

        Returns:
            List of payment records
        """
        all_payments = []

        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            for year in range(year_start, year_end + 1):
                try:
                    # Build search URL
                    params = {
                        'fips': '00000',  # All counties
                        'state': state,
                        'year': year,
                        'regionname': state
                    }

                    logger.info(f"Fetching EWG data for {state} {year}")
                    response = await client.get(self.SEARCH_URL, params=params)
                    response.raise_for_status()

                    # Parse HTML response
                    soup = BeautifulSoup(response.text, 'html.parser')
                    payment_data = self._parse_payment_page(soup, state, year)

                    if payment_data:
                        all_payments.extend(payment_data)
                        logger.info(f"Extracted {len(payment_data)} payment records for {year}")

                    # Respectful delay
                    await asyncio.sleep(settings.scrape_delay_seconds)

                except httpx.HTTPError as e:
                    logger.error(f"Error fetching EWG data for {year}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")

        return all_payments

    def _parse_payment_page(self, soup: BeautifulSoup, state: str, year: int) -> List[Dict]:
        """Parse payment data from EWG HTML page"""
        payments = []

        try:
            # Find payment tables (structure varies, this is a simplified version)
            tables = soup.find_all('table', class_='datatable')

            for table in tables:
                rows = table.find_all('tr')[1:]  # Skip header

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        payment_record = {
                            'state': state,
                            'year': year,
                            'program_name': cols[0].get_text(strip=True),
                            'total_payments': self._parse_currency(cols[1].get_text(strip=True)),
                            'recipient_count': self._parse_number(cols[2].get_text(strip=True)),
                            'average_payment': self._parse_currency(cols[3].get_text(strip=True)),
                            'source': 'EWG'
                        }
                        payments.append(payment_record)

        except Exception as e:
            logger.error(f"Error parsing EWG payment page: {e}")

        return payments

    def _parse_currency(self, value: str) -> Optional[float]:
        """Parse currency string to float"""
        try:
            cleaned = value.replace('$', '').replace(',', '').strip()
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None

    def _parse_number(self, value: str) -> Optional[int]:
        """Parse number string to int"""
        try:
            cleaned = value.replace(',', '').strip()
            return int(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None

    async def save_to_database(self, payments: List[Dict]) -> int:
        """Save EWG payment data to database"""
        saved_count = 0

        for payment in payments:
            try:
                query = """
                    INSERT INTO historical_payments (
                        program_name, year, state, total_payments,
                        recipient_count, average_payment, source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (program_name, year, state, county, source) DO UPDATE
                    SET total_payments = EXCLUDED.total_payments,
                        recipient_count = EXCLUDED.recipient_count,
                        average_payment = EXCLUDED.average_payment
                """

                params = (
                    payment['program_name'],
                    payment['year'],
                    payment['state'],
                    payment.get('total_payments'),
                    payment.get('recipient_count'),
                    payment.get('average_payment'),
                    payment['source']
                )

                with db.get_cursor() as cursor:
                    cursor.execute(query, params)
                    saved_count += 1

            except Exception as e:
                logger.error(f"Error saving EWG payment record: {e}")

        logger.info(f"Saved {saved_count} EWG payment records to database")
        return saved_count


async def run_tier1_scrapers():
    """Execute all Tier 1 API scrapers"""
    logger.info("Starting Tier 1 API scrapers...")

    # NASS QuickStats
    nass = NASSQuickStatsAPI()
    nass_data = await nass.fetch_county_data(
        state=settings.target_state,
        year_start=2018,
        year_end=2023
    )
    await nass.save_to_database(nass_data)

    # EWG Subsidy Database
    ewg = EWGSubsidyDatabase()
    ewg_payments = await ewg.fetch_state_data(
        state=settings.target_state,
        year_start=2018,
        year_end=2023
    )
    await ewg.save_to_database(ewg_payments)

    logger.info("Tier 1 API scrapers completed")


if __name__ == "__main__":
    # For testing
    asyncio.run(run_tier1_scrapers())
