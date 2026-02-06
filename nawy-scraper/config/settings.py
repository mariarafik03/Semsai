"""
Nawy Scraper Configuration Settings
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import random


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MongoDB - Primary SRV connection (requires DNS)
    mongo_uri: str = Field(
        default="mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0",
        env="MONGO_URI"
    )
    
    # MongoDB - Fallback direct connection (no DNS SRV lookup needed)
    # These are the resolved hosts from the SRV record
    mongo_uri_direct: str = Field(
        default="mongodb://semsai_user:EA-xQASp73Y9_fF@cluster0-shard-00-00.vdtyjnl.mongodb.net:27017,cluster0-shard-00-01.vdtyjnl.mongodb.net:27017,cluster0-shard-00-02.vdtyjnl.mongodb.net:27017/semsai?ssl=true&replicaSet=atlas-zq3q9v-shard-0&authSource=admin&retryWrites=true&w=majority",
        env="MONGO_URI_DIRECT"
    )
    
    database_name: str = Field(default="semsai", env="DATABASE_NAME")
    
    # Nawy URLs
    base_url: str = "https://www.nawy.com"
    compounds_url: str = "https://www.nawy.com/search"  # Uses ?page_number=X for pagination (128 pages)
    developers_url: str = "https://www.nawy.com/ar/developers"
    new_launches_url: str = "https://www.nawy.com/ar/new-launches"
    
    # Scraping Configuration
    request_delay_min: float = Field(default=3.0, env="DELAY_MIN")
    request_delay_max: float = Field(default=6.0, env="DELAY_MAX")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    timeout: int = Field(default=30000, env="TIMEOUT")  # milliseconds
    
    # Browser Settings
    headless: bool = Field(default=True, env="HEADLESS")
    slow_mo: int = Field(default=100, env="SLOW_MO")  # milliseconds between actions
    
    # Parallel Workers (careful with this)
    max_workers: int = Field(default=1, env="MAX_WORKERS")  # Start with 1 for safety
    
    # User Agents for rotation
    user_agents: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    
    # Viewport sizes for rotation
    viewports: List[dict] = [
        {"width": 1920, "height": 1080},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1366, "height": 768},
        {"width": 1280, "height": 720},
    ]
    
    # Export paths
    export_dir: str = Field(default="exports", env="EXPORT_DIR")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        extra = "ignore"
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent for anti-detection."""
        return random.choice(self.user_agents)
    
    def get_random_viewport(self) -> dict:
        """Get a random viewport size for anti-detection."""
        return random.choice(self.viewports)
    
    def get_random_delay(self) -> float:
        """Get a random delay between requests."""
        return random.uniform(self.request_delay_min, self.request_delay_max)


# Global settings instance
settings = Settings()
