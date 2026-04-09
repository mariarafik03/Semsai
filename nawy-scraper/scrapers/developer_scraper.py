"""
Developer Scraper for Nawy.com
Scrapes developer pages and their compound portfolios.
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin

from .base_scraper import BaseScraper
from config.settings import settings

logger = logging.getLogger(__name__)


class DeveloperScraper(BaseScraper):
    """
    Scraper for Nawy.com developers.
    """
    
    def __init__(self):
        super().__init__()
        self.developers_url = f"{settings.base_url}/ar/developers"
        self.scraped_developers: List[Dict] = []
    
    async def scrape_all_developers(
        self, 
        max_pages: int = None,
        max_developers: int = None
    ) -> List[Dict]:
        """Scrape all developers from Nawy."""
        await self.initialize()
        
        try:
            # Get developer URLs
            logger.info("📋 Scraping developer listings...")
            developer_urls = await self._scrape_developer_list(max_pages)
            
            if max_developers:
                developer_urls = developer_urls[:max_developers]
            
            logger.info(f"✅ Found {len(developer_urls)} developers")
            
            # Scrape each developer
            for i, url in enumerate(developer_urls, 1):
                logger.info(f"[{i}/{len(developer_urls)}] {url}")
                
                dev_data = await self._scrape_developer_detail(url)
                
                if dev_data:
                    self.scraped_developers.append(dev_data)
                    logger.info(f"   ✅ {dev_data.get('dev_name', 'Unknown')}")
                
                await self.random_delay()
            
            return self.scraped_developers
            
        finally:
            await self.close()
    
    async def _scrape_developer_list(self, max_pages: int = None) -> List[str]:
        """Get all developer page URLs."""
        urls = []
        current_page = 1
        
        while True:
            url = self.developers_url if current_page == 1 else f"{self.developers_url}?page={current_page}"
            
            if not await self.safe_goto(url):
                break
            
            await self.human_scroll(300)
            await asyncio.sleep(1)
            
            # Extract developer links
            next_data = await self.extract_next_data()
            
            if next_data:
                page_urls = self._extract_urls_from_next_data(next_data)
                urls.extend(page_urls)
            else:
                html = await self.get_page_content()
                page_urls = self._extract_urls_from_html(html)
                urls.extend(page_urls)
            
            logger.info(f"   Page {current_page}: {len(page_urls)} developers")
            
            # Check for more pages
            has_next = await self._has_next_page()
            
            if not has_next or (max_pages and current_page >= max_pages):
                break
            
            current_page += 1
            await self.random_delay()
        
        return list(set(urls))
    
    def _extract_urls_from_next_data(self, next_data: Dict) -> List[str]:
        """Extract developer URLs from __NEXT_DATA__."""
        urls = []
        
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            developers = (
                page_props.get('developers') or 
                page_props.get('data', {}).get('developers') or
                []
            )
            
            for dev in developers:
                slug = dev.get('slug') or dev.get('url_slug')
                dev_id = dev.get('id')
                
                if slug:
                    url = f"{settings.base_url}/ar/developer/{dev_id}-{slug}" if dev_id else f"{settings.base_url}/ar/developer/{slug}"
                    urls.append(url)
        except Exception as e:
            logger.debug(f"Error parsing developers: {e}")
        
        return urls
    
    def _extract_urls_from_html(self, html: str) -> List[str]:
        """Extract developer URLs from HTML."""
        urls = []
        soup = self.parse_html(html)
        
        links = soup.select('a[href*="/developer/"]')
        for link in links:
            href = link.get('href', '')
            if href:
                full_url = urljoin(settings.base_url, href)
                if '/developer/' in full_url:
                    urls.append(full_url)
        
        return list(set(urls))
    
    async def _has_next_page(self) -> bool:
        """Check for next pagination page."""
        try:
            next_btn = await self.page.query_selector(
                'a[aria-label="Next"], .pagination-next:not([disabled])'
            )
            return next_btn is not None
        except:
            return False
    
    async def _scrape_developer_detail(self, url: str) -> Optional[Dict]:
        """Scrape a developer detail page."""
        if not await self.safe_goto(url):
            return None
        
        await asyncio.sleep(2)
        
        next_data = await self.extract_next_data()
        
        if next_data:
            return self._parse_from_next_data(next_data, url)
        
        html = await self.get_page_content()
        return self._parse_from_html(html, url)
    
    def _parse_from_next_data(self, next_data: Dict, url: str) -> Optional[Dict]:
        """Parse developer from __NEXT_DATA__."""
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            dev_data = (
                page_props.get('developer') or
                page_props.get('data', {}).get('developer') or
                page_props
            )
            
            if not dev_data:
                return None
            
            # Extract compounds list
            compounds = dev_data.get('compounds', [])
            compounds_list = []
            for c in compounds:
                name = c.get('name') if isinstance(c, dict) else str(c)
                if name:
                    compounds_list.append(name)
            
            return {
                'dev_name': dev_data.get('name', ''),
                'nawy_id': str(dev_data.get('id', '')),
                'nawy_slug': dev_data.get('slug', ''),
                'nawy_url': url,
                'description': dev_data.get('description', ''),
                'logo_url': dev_data.get('logo') or dev_data.get('image', ''),
                'total_projects': dev_data.get('projects_count') or len(compounds),
                'compounds_count': len(compounds),
                'compounds_list': compounds_list,
                'website': dev_data.get('website', ''),
                'phone': dev_data.get('phone', ''),
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error parsing developer: {e}")
            return None
    
    def _parse_from_html(self, html: str, url: str) -> Optional[Dict]:
        """Parse developer from HTML (fallback)."""
        try:
            soup = self.parse_html(html)
            
            name = ''
            name_elem = soup.select_one('h1, .developer-name')
            if name_elem:
                name = self.clean_text(name_elem.get_text())
            
            if not name:
                return None
            
            # Logo
            logo = ''
            logo_elem = soup.select_one('.developer-logo img, .logo img')
            if logo_elem:
                logo = logo_elem.get('src', '')
            
            # Description
            description = ''
            desc_elem = soup.select_one('.description, .about')
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())[:1000]
            
            # Compounds count (from links or badges)
            compounds_count = 0
            count_elem = soup.select_one('.projects-count, .compounds-count')
            if count_elem:
                count_match = re.search(r'(\d+)', count_elem.get_text())
                if count_match:
                    compounds_count = int(count_match.group(1))
            
            return {
                'dev_name': name,
                'nawy_url': url,
                'logo_url': logo,
                'description': description,
                'compounds_count': compounds_count,
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None
