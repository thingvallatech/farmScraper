"""
Tier 3 PDF Processor
Downloads and extracts text and tables from PDF documents
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime

from src.config import settings
from src.database.connection import db

logger = logging.getLogger(__name__)

# Import PDF processing libraries
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    logger.warning("pdfplumber not available")
    PDFPLUMBER_AVAILABLE = False

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    logger.warning("camelot not available - table extraction may be limited")
    CAMELOT_AVAILABLE = False


class PDFProcessor:
    """Download and process PDF documents"""

    def __init__(self):
        self.pdf_dir = settings.pdf_dir
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.failed_extractions = []

    async def download_pdf(self, url: str) -> Optional[Path]:
        """
        Download PDF from URL

        Args:
            url: PDF URL

        Returns:
            Path to downloaded file, or None if failed
        """
        try:
            # Generate local filename
            filename = url.split('/')[-1]
            if not filename.endswith('.pdf'):
                filename = f"{hash(url)}.pdf"

            local_path = self.pdf_dir / filename

            # Download if not already exists
            if local_path.exists():
                logger.info(f"PDF already exists: {filename}")
                return local_path

            logger.info(f"Downloading PDF: {url}")

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Save to file
                local_path.write_bytes(response.content)

                file_size_mb = len(response.content) / (1024 * 1024)
                logger.info(f"Downloaded {filename} ({file_size_mb:.2f} MB)")

                return local_path

        except Exception as e:
            logger.error(f"Error downloading PDF {url}: {e}")
            return None

    def process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract text and tables from PDF

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with extracted content
        """
        result = {
            'text': '',
            'tables': [],
            'extraction_method': None,
            'success': False,
            'page_count': 0,
        }

        # Try pdfplumber first (fastest and most reliable)
        if PDFPLUMBER_AVAILABLE:
            try:
                result = self._extract_with_pdfplumber(pdf_path)
                if result['success']:
                    return result
            except Exception as e:
                logger.warning(f"pdfplumber extraction failed: {e}")

        # Fallback to camelot for tables
        if CAMELOT_AVAILABLE:
            try:
                tables = self._extract_tables_with_camelot(pdf_path)
                result['tables'] = tables
                result['extraction_method'] = 'camelot'
            except Exception as e:
                logger.warning(f"camelot extraction failed: {e}")

        return result

    def _extract_with_pdfplumber(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract using pdfplumber"""
        result = {
            'text': '',
            'tables': [],
            'extraction_method': 'pdfplumber',
            'success': False,
            'page_count': 0,
        }

        with pdfplumber.open(pdf_path) as pdf:
            result['page_count'] = len(pdf.pages)
            text_pages = []

            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                page_text = page.extract_text()
                if page_text:
                    text_pages.append(f"\n--- Page {page_num} ---\n{page_text}")

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    for table_num, table in enumerate(tables, 1):
                        result['tables'].append({
                            'page': page_num,
                            'table_num': table_num,
                            'data': table,
                            'headers': table[0] if table else [],
                            'rows': table[1:] if len(table) > 1 else []
                        })

            result['text'] = '\n'.join(text_pages)
            result['success'] = bool(result['text'])

        return result

    def _extract_tables_with_camelot(self, pdf_path: Path) -> List[Dict]:
        """Extract tables using camelot"""
        tables_data = []

        try:
            tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice')

            for idx, table in enumerate(tables, 1):
                df = table.df

                tables_data.append({
                    'table_num': idx,
                    'page': table.page,
                    'data': df.values.tolist(),
                    'headers': df.columns.tolist(),
                    'rows': df.values.tolist(),
                })

        except Exception as e:
            logger.error(f"Camelot table extraction error: {e}")

        return tables_data

    def extract_payment_tables(self, tables: List[Dict]) -> List[Dict]:
        """
        Identify and structure payment rate tables

        Args:
            tables: List of extracted tables

        Returns:
            List of tables that appear to contain payment information
        """
        payment_tables = []

        for table in tables:
            # Get headers (first row or explicit headers field)
            headers = table.get('headers', [])
            if not headers and table.get('data'):
                headers = table['data'][0] if table['data'] else []

            # Convert headers to string for searching
            headers_str = ' '.join(str(h).lower() for h in headers if h)

            # Payment-related keywords
            payment_keywords = [
                'payment', 'rate', 'amount', '$', 'per acre',
                'subsidy', 'cost', 'price', 'reimbursement'
            ]

            # Check if table contains payment information
            if any(keyword in headers_str for keyword in payment_keywords):
                payment_tables.append({
                    'page': table.get('page'),
                    'table_num': table.get('table_num'),
                    'headers': headers,
                    'data': table.get('rows', table.get('data', [])),
                    'table_type': 'payment_rates'
                })

        return payment_tables

    async def save_to_database(
        self,
        url: str,
        local_path: Path,
        extracted_data: Dict
    ) -> Optional[int]:
        """Save PDF and extracted data to database"""
        try:
            file_size_mb = local_path.stat().st_size / (1024 * 1024)

            query = """
                INSERT INTO documents (
                    source_url, file_name, file_type, file_size_mb, local_path,
                    text_extracted, tables_extracted, extraction_method, page_count,
                    full_text, tables, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO UPDATE
                SET download_timestamp = NOW(),
                    full_text = EXCLUDED.full_text,
                    tables = EXCLUDED.tables,
                    text_extracted = EXCLUDED.text_extracted,
                    tables_extracted = EXCLUDED.tables_extracted
                RETURNING id
            """

            from psycopg2.extras import Json

            with db.get_cursor() as cursor:
                cursor.execute(query, (
                    url,
                    local_path.name,
                    'pdf',
                    file_size_mb,
                    str(local_path),
                    extracted_data['success'],
                    bool(extracted_data['tables']),
                    extracted_data['extraction_method'],
                    extracted_data['page_count'],
                    extracted_data['text'],
                    Json(extracted_data['tables']),
                    Json({'processed_at': datetime.now().isoformat()})
                ))

                result = cursor.fetchone()
                return result['id'] if result else None

        except Exception as e:
            logger.error(f"Error saving PDF to database: {e}")
            return None

    async def process_pdf_url(self, url: str) -> bool:
        """
        Download and process a single PDF

        Args:
            url: PDF URL

        Returns:
            True if successful
        """
        try:
            # Download
            local_path = await self.download_pdf(url)
            if not local_path:
                return False

            # Respectful delay
            await asyncio.sleep(settings.scrape_delay_seconds)

            # Extract
            extracted_data = self.process_pdf(local_path)

            # Save to database
            await self.save_to_database(url, local_path, extracted_data)

            logger.info(
                f"Processed PDF: {local_path.name} "
                f"(success: {extracted_data['success']}, "
                f"tables: {len(extracted_data['tables'])})"
            )

            return extracted_data['success']

        except Exception as e:
            logger.error(f"Error processing PDF {url}: {e}")
            self.failed_extractions.append(url)
            return False


async def process_discovered_pdfs():
    """Process all discovered PDFs"""
    logger.info("Starting PDF processing...")

    # Get PDF URLs from discovery job
    query = """
        SELECT jsonb_array_elements_text(metadata->'pdf_urls') as pdf_url
        FROM scrape_jobs
        WHERE job_type = 'discovery'
        ORDER BY completed_at DESC
        LIMIT 1
    """

    results = db.fetch_all(query)
    pdf_urls = [r['pdf_url'] for r in results]

    logger.info(f"Found {len(pdf_urls)} PDFs to process")

    processor = PDFProcessor()

    # Process PDFs with concurrency limit
    semaphore = asyncio.Semaphore(settings.max_concurrent_requests)

    async def process_with_semaphore(url):
        async with semaphore:
            return await processor.process_pdf_url(url)

    # Process all PDFs
    tasks = [process_with_semaphore(url) for url in pdf_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if r is True)
    logger.info(
        f"PDF processing complete: {success_count}/{len(pdf_urls)} successful, "
        f"{len(processor.failed_extractions)} failed"
    )


if __name__ == "__main__":
    # For testing
    asyncio.run(process_discovered_pdfs())
