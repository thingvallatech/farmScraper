"""
Main Pipeline Orchestrator
Executes the complete FSA data collection pipeline
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import logger
from src.config import settings
from src.database.connection import db

# Import scrapers
from src.scrapers.tier1_api import run_tier1_scrapers
from src.scrapers.discovery import run_discovery_crawler
from src.scrapers.extractor import process_discovered_pages
from src.scrapers.pdf_processor import process_discovered_pdfs

# Import analyzer
from src.analyzers.data_analyzer import run_data_analysis


class FSADataPipeline:
    """Main pipeline orchestrator"""

    def __init__(self):
        self.start_time = datetime.now()
        self.job_id = None

    async def initialize_database(self):
        """Initialize database connection"""
        try:
            logger.info("Initializing database connection...")
            db.connect()
            logger.info("Database connection established")

            # Create job record
            self.job_id = db.insert('scrape_jobs', {
                'job_type': 'full_pipeline',
                'status': 'running',
                'started_at': self.start_time,
                'metadata': {}
            })

            logger.info(f"Pipeline job created: {self.job_id}")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def run_tier1(self):
        """Execute Tier 1: API sources"""
        if not settings.enable_tier1:
            logger.info("Tier 1 (APIs) disabled - skipping")
            return

        logger.info("=" * 80)
        logger.info("TIER 1: API DATA COLLECTION")
        logger.info("=" * 80)

        try:
            await run_tier1_scrapers()
            logger.info("Tier 1 complete")
        except Exception as e:
            logger.error(f"Tier 1 failed: {e}", exc_info=True)

    async def run_tier2(self):
        """Execute Tier 2: Web scraping"""
        if not settings.enable_tier2:
            logger.info("Tier 2 (Web Scraping) disabled - skipping")
            return

        logger.info("=" * 80)
        logger.info("TIER 2: WEB SCRAPING")
        logger.info("=" * 80)

        try:
            # Discovery crawl
            logger.info("Starting discovery crawl...")
            crawler = await run_discovery_crawler()

            logger.info(f"Discovery complete: {len(crawler.visited_urls)} pages found")

            # Extract program data
            logger.info("Extracting program data...")
            await process_discovered_pages()

            logger.info("Tier 2 complete")

        except Exception as e:
            logger.error(f"Tier 2 failed: {e}", exc_info=True)

    async def run_tier3(self):
        """Execute Tier 3: PDF processing"""
        if not settings.enable_tier3:
            logger.info("Tier 3 (PDF Processing) disabled - skipping")
            return

        logger.info("=" * 80)
        logger.info("TIER 3: PDF PROCESSING")
        logger.info("=" * 80)

        try:
            await process_discovered_pdfs()
            logger.info("Tier 3 complete")
        except Exception as e:
            logger.error(f"Tier 3 failed: {e}", exc_info=True)

    async def analyze_results(self):
        """Execute data analysis and generate report"""
        logger.info("=" * 80)
        logger.info("DATA ANALYSIS")
        logger.info("=" * 80)

        try:
            await run_data_analysis()
            logger.info("Analysis complete")
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)

    async def finalize(self):
        """Finalize pipeline execution"""
        end_time = datetime.now()
        duration = end_time - self.start_time

        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total runtime: {duration}")

        # Update job record
        if self.job_id:
            try:
                db.update(
                    'scrape_jobs',
                    {
                        'status': 'completed',
                        'completed_at': end_time
                    },
                    'id = %s',
                    (self.job_id,)
                )
            except Exception as e:
                logger.error(f"Error updating job record: {e}")

        # Close database connection
        db.close()

        logger.info(f"Report saved to: {settings.data_dir / 'extraction_report.txt'}")
        logger.info(f"Logs saved to: {settings.log_dir}")

    async def run(self):
        """Execute complete data collection pipeline"""
        try:
            logger.info("=" * 80)
            logger.info("FARM ASSIST - FSA DATA COLLECTION PIPELINE")
            logger.info("=" * 80)
            logger.info(f"Start time: {self.start_time}")
            logger.info(f"Target state: {settings.target_state}")
            logger.info(f"Configuration:")
            logger.info(f"  - Tier 1 (APIs): {settings.enable_tier1}")
            logger.info(f"  - Tier 2 (Web): {settings.enable_tier2}")
            logger.info(f"  - Tier 3 (PDFs): {settings.enable_tier3}")
            logger.info(f"  - Scrape delay: {settings.scrape_delay_seconds}s")
            logger.info(f"  - Max depth: {settings.max_crawl_depth}")
            logger.info("")

            # Initialize
            await self.initialize_database()

            # Execute tiers sequentially
            await self.run_tier1()
            await self.run_tier2()
            await self.run_tier3()

            # Analyze results
            await self.analyze_results()

            # Finalize
            await self.finalize()

        except KeyboardInterrupt:
            logger.warning("Pipeline interrupted by user")
            if self.job_id:
                db.update('scrape_jobs', {'status': 'interrupted'}, 'id = %s', (self.job_id,))
            db.close()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            if self.job_id:
                db.update(
                    'scrape_jobs',
                    {'status': 'failed', 'error_log': str(e)},
                    'id = %s',
                    (self.job_id,)
                )
            db.close()
            raise


async def run_pipeline():
    """Main entry point"""
    pipeline = FSADataPipeline()
    await pipeline.run()


if __name__ == "__main__":
    # Install playwright browsers if needed
    try:
        from playwright.async_api import async_playwright

        logger.info("Checking Playwright installation...")

    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install")
        sys.exit(1)

    # Run pipeline
    try:
        asyncio.run(run_pipeline())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
