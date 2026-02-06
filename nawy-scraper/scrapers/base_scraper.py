"""
Base Scraper with Anti-Detection and Browser Management
"""
import asyncio
import json
import random
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)


class BaseScraper:
    """
    Base scraper class with Playwright browser management and anti-detection.
    
    Features:
    - Human-like delays and behavior
    - User-agent and viewport rotation
    - Retry logic with exponential backoff
    - Next.js __NEXT_DATA__ extraction
    - Page content parsing with BeautifulSoup
    """
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_initialized = False
    
    async def initialize(self):
        """Initialize Playwright browser with anti-detection settings."""
        if self._is_initialized:
            return
        
        logger.info("🚀 Initializing browser...")
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth options
        self.browser = await self.playwright.chromium.launch(
            headless=settings.headless,
            slow_mo=settings.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Create context with random user agent and viewport
        viewport = settings.get_random_viewport()
        user_agent = settings.get_random_user_agent()
        
        self.context = await self.browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale='ar-EG',
            timezone_id='Africa/Cairo',
            permissions=['geolocation'],
            geolocation={'latitude': 30.0444, 'longitude': 31.2357},  # Cairo
        )
        
        # Add anti-detection scripts
        await self.context.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ar-EG', 'ar', 'en-US', 'en']
            });
            
            // Override chrome property
            window.chrome = {
                runtime: {}
            };
        """)
        
        self.page = await self.context.new_page()
        self._is_initialized = True
        
        logger.info(f"✅ Browser initialized (UA: {user_agent[:50]}...)")
    
    async def close(self):
        """Close browser and cleanup resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        self._is_initialized = False
        logger.info("🔌 Browser closed")
    
    async def random_delay(self, min_sec: float = None, max_sec: float = None):
        """Wait for a random duration to mimic human behavior."""
        min_sec = min_sec or settings.request_delay_min
        max_sec = max_sec or settings.request_delay_max
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def human_scroll(self, scroll_amount: int = None):
        """Scroll the page like a human would."""
        if not scroll_amount:
            scroll_amount = random.randint(200, 600)
        
        await self.page.evaluate(f"""
            window.scrollBy({{
                top: {scroll_amount},
                behavior: 'smooth'
            }});
        """)
        await asyncio.sleep(random.uniform(0.3, 0.8))
    
    async def safe_goto(self, url: str, retries: int = None) -> bool:
        """
        Navigate to URL with retry logic and error handling.
        
        Returns True if successful, False otherwise.
        """
        retries = retries or settings.max_retries
        
        for attempt in range(retries):
            try:
                logger.info(f"📄 Navigating to: {url[:80]}...")
                
                response = await self.page.goto(
                    url,
                    timeout=settings.timeout or 60000,
                    wait_until='domcontentloaded'  # Changed from networkidle to be faster
                )
                
                if response and response.status == 200:
                    # Wait for content to load
                    await self.page.wait_for_load_state('domcontentloaded')
                    await asyncio.sleep(1)  # Extra wait for dynamic content
                    return True
                
                if response and response.status == 429:
                    logger.warning("⚠️ Rate limited (429). Waiting 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                
                if response and response.status == 403:
                    logger.error("❌ Access forbidden (403). May be blocked.")
                    return False
                
                logger.warning(f"⚠️ Status {response.status if response else 'None'}")
                
            except Exception as e:
                logger.error(f"❌ Navigation error (attempt {attempt + 1}): {e}")
                
                if attempt < retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.info(f"⏳ Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
        
        return False
    
    async def get_page_content(self) -> str:
        """Get current page HTML content."""
        return await self.page.content()
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML with BeautifulSoup."""
        return BeautifulSoup(html, 'lxml')
    
    async def extract_next_data(self) -> Optional[Dict]:
        """
        Extract __NEXT_DATA__ from Next.js pages.
        This often contains all the page data in JSON format.
        """
        try:
            next_data = await self.page.query_selector('script#__NEXT_DATA__')
            if next_data:
                json_text = await next_data.inner_text()
                return json.loads(json_text)
        except Exception as e:
            logger.debug(f"No __NEXT_DATA__ found: {e}")
        
        return None
    
    async def extract_json_from_script(self, pattern: str = None) -> List[Dict]:
        """
        Extract JSON data from script tags.
        Useful for finding embedded data in the page.
        """
        results = []
        
        try:
            scripts = await self.page.query_selector_all('script')
            
            for script in scripts:
                text = await script.inner_text()
                
                # Skip empty scripts
                if not text or len(text) < 10:
                    continue
                
                # If pattern provided, check for it
                if pattern and pattern not in text:
                    continue
                
                # Try to extract JSON
                import re
                json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
                
                for match in json_matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict) and len(data) > 2:
                            results.append(data)
                    except:
                        pass
        
        except Exception as e:
            logger.debug(f"Error extracting JSON from scripts: {e}")
        
        return results
    
    async def intercept_api_calls(self, url_pattern: str = None) -> List[Dict]:
        """
        Intercept XHR/Fetch API calls and capture responses.
        Useful for discovering hidden API endpoints.
        """
        captured_responses = []
        
        async def handle_response(response):
            if response.request.resource_type in ['xhr', 'fetch']:
                url = response.url
                
                # Filter by pattern if provided
                if url_pattern and url_pattern not in url:
                    return
                
                try:
                    if 'application/json' in response.headers.get('content-type', ''):
                        body = await response.json()
                        captured_responses.append({
                            'url': url,
                            'method': response.request.method,
                            'status': response.status,
                            'data': body
                        })
                        logger.debug(f"📡 Captured API: {url[:60]}")
                except:
                    pass
        
        self.page.on('response', handle_response)
        return captured_responses
    
    async def wait_for_selector_safe(
        self, 
        selector: str, 
        timeout: int = 10000
    ) -> bool:
        """Wait for selector with timeout, return False if not found."""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except:
            return False
    
    async def click_and_wait(self, selector: str, wait_time: float = 1.0):
        """Click an element and wait for page to settle."""
        try:
            await self.page.click(selector)
            await asyncio.sleep(wait_time)
            await self.page.wait_for_load_state('networkidle', timeout=5000)
        except Exception as e:
            logger.debug(f"Click error on {selector}: {e}")
    
    async def scroll_to_bottom(self, max_scrolls: int = 10):
        """Scroll to bottom of page to load all content (infinite scroll)."""
        for _ in range(max_scrolls):
            previous_height = await self.page.evaluate('document.body.scrollHeight')
            
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1.5)
            
            new_height = await self.page.evaluate('document.body.scrollHeight')
            
            if new_height == previous_height:
                break
            
            await self.human_scroll()
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from Arabic/English text."""
        if not price_text:
            return None
        
        import re
        
        # Remove currency symbols and non-numeric chars except digits and decimal
        cleaned = re.sub(r'[^\d.,]', '', price_text)
        
        # Handle Arabic numerals
        arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
        cleaned = cleaned.translate(arabic_to_english)
        
        # Remove thousand separators and normalize decimal
        cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except:
            return None
    
    def parse_area(self, area_text: str) -> Optional[float]:
        """Parse area (sqm) from text."""
        return self.parse_price(area_text)  # Same logic works
    
    async def take_screenshot(self, name: str = None):
        """Take a screenshot (useful for debugging)."""
        name = name or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = f"exports/{name}.png"
        await self.page.screenshot(path=path, full_page=True)
        logger.info(f"📸 Screenshot saved: {path}")
