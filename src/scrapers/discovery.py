"""
Tier 2 Discovery Crawler
Breadth-first crawl of FSA website to discover program pages and PDFs
"""
import asyncio
import logging
from typing import Set, List, Dict, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser

from src.config import settings
from src.database.connection import db

logger = logging.getLogger(__name__)


class FSADiscoveryCrawler:
    """
    Discovery crawler for FSA website
    Finds program pages and PDFs using breadth-first search
    """

    def __init__(self, resume: bool = True):
        self.max_depth = settings.max_crawl_depth
        self.delay = settings.scrape_delay_seconds

        # Load already-visited URLs from database for resume capability
        if resume:
            self.visited_urls = self._load_visited_urls_from_db()
            logger.info(f"Resuming: Loaded {len(self.visited_urls)} already-visited URLs from database")
        else:
            self.visited_urls: Set[str] = set()

        self.to_visit: List[Tuple[str, int]] = []  # (url, depth)
        self.pdf_urls: Set[str] = set()
        self.program_pages: Set[str] = set()

    async def crawl(
        self,
        start_url: str = "https://www.fsa.usda.gov/programs-and-services/",
        state_url: str = "https://www.fsa.usda.gov/state-offices/North-Dakota/"
    ):
        """
        Execute breadth-first crawl

        Args:
            start_url: Main programs page
            state_url: State-specific page
        """
        logger.info(f"Starting discovery crawl from {start_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                # Crawl main programs section
                await self._crawl_from_seed(browser, start_url, "programs")

                # Crawl state-specific section
                await self._crawl_from_seed(browser, state_url, "state")

                # Save all discoveries
                await self.save_discoveries()

                logger.info(
                    f"Discovery complete: {len(self.visited_urls)} pages, "
                    f"{len(self.pdf_urls)} PDFs, {len(self.program_pages)} program pages"
                )

            finally:
                await browser.close()

    async def _crawl_from_seed(self, browser: Browser, seed_url: str, section: str):
        """Crawl from a seed URL"""
        self.to_visit.append((seed_url, 0))

        while self.to_visit:
            url, depth = self.to_visit.pop(0)

            if url in self.visited_urls or depth > self.max_depth:
                continue

            page = await browser.new_page()
            try:
                await self.crawl_page(page, url, depth, section)
            finally:
                await page.close()

            # Respectful delay
            await asyncio.sleep(self.delay)

    async def crawl_page(self, page: Page, url: str, depth: int, section: str):
        """
        Crawl a single page

        Args:
            page: Playwright page object
            url: URL to crawl
            depth: Current depth in crawl tree
            section: Section identifier ('programs' or 'state')
        """
        if url in self.visited_urls:
            return

        self.visited_urls.add(url)

        try:
            logger.info(f"Crawling [{depth}]: {url}")

            # Navigate to page
            response = await page.goto(url, wait_until='networkidle', timeout=30000)

            if not response or response.status != 200:
                logger.warning(f"Failed to load {url}: status {response.status if response else 'N/A'}")
                return

            # Extract page content
            content = await page.content()
            text = await page.evaluate('() => document.body.innerText')
            title = await page.title()

            # Extract all links
            links = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href && href.startsWith('http'))
            ''')

            # Classify links
            for link in links:
                self._classify_link(link, depth)

            # Check if this is a program page
            if self._is_program_page(text, url):
                self.program_pages.add(url)

            # Save to database
            domain = urlparse(url).netloc
            await self._save_page_to_db(
                url=url,
                domain=domain,
                status_code=response.status,
                page_title=title,
                raw_html=content,
                raw_text=text,
                links=links,
                section=section
            )

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")

    def _classify_link(self, link: str, current_depth: int):
        """Classify and queue links"""
        link_lower = link.lower()

        # PDF files
        if '.pdf' in link_lower:
            self.pdf_urls.add(link)
            logger.debug(f"Found PDF: {link}")

        # FSA program pages
        elif 'fsa.usda.gov' in link and any(
            keyword in link_lower for keyword in [
                'program', 'assistance', 'loan', 'insurance',
                'conservation', 'disaster', 'payment', 'subsidy'
            ]
        ):
            if link not in self.visited_urls:
                self.to_visit.append((link, current_depth + 1))

    def _is_program_page(self, text: str, url: str) -> bool:
        """
        Determine if page describes a specific program

        Args:
            text: Page text content
            url: Page URL

        Returns:
            True if this appears to be a program description page
        """
        text_lower = text.lower()

        # Keywords that suggest program information
        program_indicators = [
            'eligibility',
            'payment rate',
            'how to apply',
            'deadline',
            'enrollment',
            'program description',
            'benefits',
            'requirements'
        ]

        # Must have several indicators
        indicator_count = sum(1 for indicator in program_indicators if indicator in text_lower)

        # URL should contain program-related path
        url_has_program = any(
            keyword in url.lower()
            for keyword in ['program', 'assistance', 'loan', 'insurance']
        )

        return indicator_count >= 3 and url_has_program

    def _load_visited_urls_from_db(self) -> Set[str]:
        """Load already-crawled URLs from database for resume capability"""
        try:
            query = "SELECT url FROM raw_pages"
            results = db.fetch_all(query)
            return set(row['url'] for row in results)
        except Exception as e:
            logger.warning(f"Could not load visited URLs from database: {e}")
            return set()

    async def _save_page_to_db(self, **kwargs):
        """Save page data to database"""
        try:
            page_id = db.upsert_raw_page(
                url=kwargs['url'],
                domain=kwargs['domain'],
                status_code=kwargs['status_code'],
                page_title=kwargs['page_title'],
                raw_html=kwargs['raw_html'],
                raw_text=kwargs['raw_text'],
                links=kwargs['links'],
                metadata={'section': kwargs['section'], 'crawl_time': datetime.now().isoformat()}
            )
            logger.debug(f"Saved page {page_id}: {kwargs['url']}")
        except Exception as e:
            logger.error(f"Error saving page to database: {e}")

    async def save_discoveries(self):
        """Save discovered URLs summary to database"""
        try:
            summary = {
                'total_pages': len(self.visited_urls),
                'pdf_count': len(self.pdf_urls),
                'program_pages': len(self.program_pages),
                'pdf_urls': list(self.pdf_urls),
                'program_page_urls': list(self.program_pages)
            }

            query = """
                INSERT INTO scrape_jobs (job_type, status, completed_at, total_items, metadata)
                VALUES (%s, %s, %s, %s, %s)
            """

            with db.get_cursor() as cursor:
                cursor.execute(
                    query,
                    ('discovery', 'completed', datetime.now(),
                     len(self.visited_urls), summary)
                )

            logger.info("Saved discovery summary to database")

        except Exception as e:
            logger.error(f"Error saving discoveries: {e}")


async def run_discovery_crawler():
    """Execute discovery crawler"""
    crawler = FSADiscoveryCrawler()
    await crawler.crawl()
    return crawler


if __name__ == "__main__":
    # For testing
    asyncio.run(run_discovery_crawler())
