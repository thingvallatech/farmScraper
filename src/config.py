"""
Configuration management for Farm Assist scraper
Loads settings from environment variables with validation
"""
from pathlib import Path
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'  # Ignore pgadmin and other extra environment variables
    )

    # Database
    postgres_user: str = Field(default="farm_user")
    postgres_password: str = Field(default="farm_password")
    postgres_db: str = Field(default="farm_scraper")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse DATABASE_URL if present (for Digital Ocean, Heroku, etc.)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            try:
                # Parse postgresql://user:password@host:port/database
                from urllib.parse import urlparse
                result = urlparse(database_url)
                self.postgres_user = result.username or self.postgres_user
                self.postgres_password = result.password or self.postgres_password
                self.postgres_host = result.hostname or self.postgres_host
                self.postgres_port = result.port or self.postgres_port
                self.postgres_db = result.path.lstrip('/') or self.postgres_db
            except Exception as e:
                # If parsing fails, use defaults
                print(f"Warning: Could not parse DATABASE_URL: {e}")

    # API Keys
    nass_api_key: str = Field(default="")

    # Scraping Configuration
    target_state: str = Field(default="ND")
    scrape_delay_seconds: float = Field(default=2.5)
    max_crawl_depth: int = Field(default=3)
    user_agent: str = Field(
        default="Farm Assist Data Collector (Research/Educational Purpose)"
    )

    # Storage Paths
    data_dir: Path = Field(default=Path("./data"))
    pdf_dir: Path = Field(default=Path("./data/pdfs"))
    raw_dir: Path = Field(default=Path("./data/raw"))
    log_dir: Path = Field(default=Path("./logs"))

    # Logging
    log_level: str = Field(default="INFO")
    log_format: Literal["json", "text"] = Field(default="json")

    # Pipeline Configuration
    enable_tier1: bool = Field(default=True)
    enable_tier2: bool = Field(default=True)
    enable_tier3: bool = Field(default=True)
    max_concurrent_requests: int = Field(default=3)
    timeout_seconds: int = Field(default=30)

    # Analysis Configuration
    confidence_threshold: float = Field(default=0.7)
    min_payment_programs: int = Field(default=30)
    min_eligibility_programs: int = Field(default=40)
    min_deadline_programs: int = Field(default=25)

    @validator('data_dir', 'pdf_dir', 'raw_dir', 'log_dir', pre=True)
    def ensure_path(cls, v):
        """Convert string paths to Path objects"""
        if isinstance(v, str):
            return Path(v)
        return v

    @property
    def database_url(self) -> str:
        """Generate PostgreSQL connection URL"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        for directory in [self.data_dir, self.pdf_dir, self.raw_dir, self.log_dir]:
            directory.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

# Ensure directories exist on import
settings.ensure_directories()
