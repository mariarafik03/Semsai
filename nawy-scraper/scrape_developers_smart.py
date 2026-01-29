"""
Smart Developer Scraper
========================

Scrapes ONLY developers that are NOT in MongoDB.
Similar to scrape_smart.py but for developers.

Usage:
    python scrape_developers_smart.py
"""

import asyncio
import json
import sys
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Set

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from scrapers.base_scraper import BaseScraper
from database.connection import db_client
from utils.data_cleaner import DataCleaner
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('scraper_developers.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)

# Progress file for developers
PROGRESS_FILE = "developer_progress.json"


class SmartDeveloperScraper(BaseScraper):
    """Smart Developer Scraper with MongoDB checking and resume capability."""
    
    def __init__(self):
        super().__init__()
        self.developers_url = f"{settings.base_url}/developer"
        self.scraped_developers: List[Dict] = []
        self.progress_file = PROGRESS_FILE
    
    def _save_progress(self, data: Dict):
        """Save progress to checkpoint file."""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"💾 Progress saved to {self.progress_file}")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def _load_progress(self) -> Optional[Dict]:
        """Load progress from checkpoint file."""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📂 Loaded progress from {self.progress_file}")
                return data
        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
        return None
    
    async def scrape_developer_urls(self) -> List[str]:
        """Scrape all developer URLs from the listing page."""
        await self.initialize()
        
        all_urls = []
        current_page = 1
        
        try:
            while True:
                url = self.developers_url if current_page == 1 else f"{self.developers_url}?page={current_page}"
                
                logger.info(f"📄 Scraping developer list page {current_page}...")
                
                if not await self.safe_goto(url):
                    break
                
                await self.human_scroll(500)
                await asyncio.sleep(2)
                
                # Extract from __NEXT_DATA__
                next_data = await self.extract_next_data()
                page_urls = []
                
                if next_data:
                    page_urls = self._extract_urls_from_next_data(next_data)
                
                if not page_urls:
                    # Fallback to HTML parsing
                    html = await self.get_page_content()
                    page_urls = self._extract_urls_from_html(html)
                
                if not page_urls:
                    logger.info(f"   No developers on page {current_page}, stopping.")
                    break
                
                all_urls.extend(page_urls)
                logger.info(f"   Page {current_page}: {len(page_urls)} developers (total: {len(all_urls)})")
                
                # Check for next page
                has_next = await self._has_next_page()
                
                if not has_next:
                    break
                
                current_page += 1
                await self.random_delay()
        
        finally:
            await self.close()
        
        # Remove duplicates
        unique_urls = list(set(all_urls))
        logger.info(f"✅ Found {len(unique_urls)} unique developer URLs")
        
        return unique_urls
    
    def _extract_urls_from_next_data(self, next_data: Dict) -> List[str]:
        """Extract developer URLs from __NEXT_DATA__."""
        urls = []
        
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            developers = (
                page_props.get('developers') or 
                page_props.get('data', {}).get('developers') or
                page_props.get('allDevelopers') or
                []
            )
            
            for dev in developers:
                slug = dev.get('slug') or dev.get('url_slug')
                dev_id = dev.get('id')
                
                if slug and dev_id:
                    url = f"{settings.base_url}/developer/{dev_id}-{slug}"
                    urls.append(url)
                elif slug:
                    url = f"{settings.base_url}/developer/{slug}"
                    urls.append(url)
        except Exception as e:
            logger.debug(f"Error parsing developers: {e}")
        
        return urls
    
    def _extract_urls_from_html(self, html: str) -> List[str]:
        """Extract developer URLs from HTML."""
        urls = []
        soup = self.parse_html(html)
        
        # Find all developer links
        links = soup.select('a[href*="/developer/"]')
        for link in links:
            href = link.get('href', '')
            if href and '/developer/' in href:
                # Build full URL
                if href.startswith('/'):
                    full_url = f"{settings.base_url}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = f"{settings.base_url}/{href}"
                
                # Skip the main developers page
                if full_url.rstrip('/') != f"{settings.base_url}/developer":
                    urls.append(full_url)
        
        return list(set(urls))
    
    async def _has_next_page(self) -> bool:
        """Check for next pagination page."""
        try:
            next_btn = await self.page.query_selector(
                'a[aria-label="Next"], button[aria-label="Next"], .pagination-next:not([disabled])'
            )
            return next_btn is not None
        except:
            return False
    
    async def scrape_developer_detail(self, url: str) -> Optional[Dict]:
        """Scrape a single developer detail page."""
        if not await self.safe_goto(url):
            return None
        
        await asyncio.sleep(2)
        await self.human_scroll(300)
        
        next_data = await self.extract_next_data()
        
        if next_data:
            return self._parse_developer_from_next_data(next_data, url)
        
        html = await self.get_page_content()
        return self._parse_developer_from_html(html, url)
    
    def _parse_developer_from_next_data(self, next_data: Dict, url: str) -> Optional[Dict]:
        """Parse developer from __NEXT_DATA__."""
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            dev_data = (
                page_props.get('developer') or
                page_props.get('data', {}).get('developer') or
                page_props.get('developerDetails') or
                page_props
            )
            
            if not dev_data:
                return None
            
            # Extract developer name
            name = dev_data.get('name', '')
            if not name:
                return None
            
            # Extract description (convert HTML to text)
            description = dev_data.get('description', '')
            if description:
                description = DataCleaner.html_to_text(description)
            
            # Extract areas
            areas = []
            areas_data = dev_data.get('areas', []) or dev_data.get('locations', [])
            for area in areas_data:
                area_name = area.get('name') if isinstance(area, dict) else str(area)
                if area_name:
                    areas.append(area_name)
            
            # Extract compounds
            compounds = dev_data.get('compounds', []) or dev_data.get('projects', [])
            compound_names = []
            compound_ids = []
            for c in compounds:
                if isinstance(c, dict):
                    c_name = c.get('name')
                    c_id = c.get('id')
                    if c_name:
                        compound_names.append(c_name)
                    if c_id:
                        compound_ids.append(str(c_id))
                else:
                    compound_names.append(str(c))
            
            # Extract price range
            price_min = None
            price_max = None
            price_data = dev_data.get('price', {})
            if isinstance(price_data, dict):
                price_min = price_data.get('min') or price_data.get('from')
                price_max = price_data.get('max') or price_data.get('to')
            elif isinstance(price_data, (int, float)):
                price_min = price_data
            
            # Also check for minPrice/maxPrice
            if not price_min:
                price_min = dev_data.get('minPrice') or dev_data.get('min_price')
            if not price_max:
                price_max = dev_data.get('maxPrice') or dev_data.get('max_price')
            
            return {
                'dev_name': name,
                'nawy_id': str(dev_data.get('id', '')),
                'nawy_slug': dev_data.get('slug', ''),
                'nawy_url': url,
                'description': description[:5000] if description else '',
                'logo_url': dev_data.get('logo') or dev_data.get('image', ''),
                'areas': areas,
                'price_min': price_min,
                'price_max': price_max,
                'total_projects': dev_data.get('projects_count') or len(compounds),
                'compounds_count': len(compound_names),
                'compound_names': compound_names,
                'compound_ids': compound_ids,
                'website': dev_data.get('website', ''),
                'phone': dev_data.get('phone', ''),
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error parsing developer: {e}")
            return None
    
    def _parse_developer_from_html(self, html: str, url: str) -> Optional[Dict]:
        """Parse developer from HTML (fallback)."""
        try:
            soup = self.parse_html(html)
            
            # Name
            name = ''
            name_elem = soup.select_one('h1, .developer-name, [class*="title"]')
            if name_elem:
                name = self.clean_text(name_elem.get_text())
            
            if not name:
                return None
            
            # Logo
            logo = ''
            logo_elem = soup.select_one('.developer-logo img, .logo img, img[alt*="logo"]')
            if logo_elem:
                logo = logo_elem.get('src', '')
            
            # Description
            description = ''
            desc_elem = soup.select_one('.description, .about, [class*="about"]')
            if desc_elem:
                description = DataCleaner.html_to_text(desc_elem.get_text())[:5000]
            
            # Extract nawy_id from URL
            nawy_id = ''
            slug = ''
            match = re.search(r'/developer/(\d+)-(.+?)(?:\?|$|/)', url)
            if match:
                nawy_id = match.group(1)
                slug = match.group(2)
            
            return {
                'dev_name': name,
                'nawy_id': nawy_id,
                'nawy_slug': slug,
                'nawy_url': url,
                'logo_url': logo,
                'description': description,
                'scraped_at': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return None


def get_existing_developer_ids() -> tuple:
    """Get all developer nawy_ids and URLs that are already in MongoDB."""
    try:
        developers_col = db_client._db['developers']
        existing = developers_col.find({}, {'nawy_id': 1, 'nawy_url': 1})
        
        existing_ids = set()
        existing_urls = set()
        
        for doc in existing:
            if doc.get('nawy_id'):
                existing_ids.add(str(doc['nawy_id']))
            if doc.get('nawy_url'):
                existing_urls.add(doc['nawy_url'])
        
        return existing_ids, existing_urls
    except Exception as e:
        logger.error(f"Error getting existing developers: {e}")
        return set(), set()


def extract_nawy_id_from_url(url: str) -> Optional[str]:
    """Extract nawy_id from URL like /developer/123-name"""
    try:
        match = re.search(r'/developer/(\d+)-', url)
        if match:
            return match.group(1)
    except:
        pass
    return None


async def scrape_missing_developers():
    """Scrape only developers that are not in MongoDB."""
    
    console.print("\n[bold cyan]🏢 Smart Developer Scraper[/bold cyan]")
    console.print("[dim]Scrapes ONLY missing developers from MongoDB[/dim]\n")
    
    scraper = SmartDeveloperScraper()
    
    # Check for existing progress
    progress = scraper._load_progress()
    developer_urls = []
    
    if progress and progress.get('developer_urls'):
        developer_urls = progress['developer_urls']
        console.print(f"   📂 Loaded {len(developer_urls)} URLs from progress file")
    else:
        # Scrape developer URLs
        console.print("   📋 Scraping developer list...")
        developer_urls = await scraper.scrape_developer_urls()
        
        # Save URLs
        scraper._save_progress({
            'developer_urls': developer_urls,
            'last_scraped_index': 0,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    console.print(f"   Total developer URLs: {len(developer_urls)}")
    
    # Get existing developers from MongoDB
    existing_ids, existing_urls = get_existing_developer_ids()
    console.print(f"   Existing in MongoDB: {len(existing_urls)} developers")
    
    # Find missing URLs
    missing_urls = []
    for url in developer_urls:
        # Check by URL
        if url in existing_urls:
            continue
        
        # Check by nawy_id
        nawy_id = extract_nawy_id_from_url(url)
        if nawy_id and nawy_id in existing_ids:
            continue
        
        missing_urls.append(url)
    
    console.print(f"   [bold yellow]Missing developers to scrape: {len(missing_urls)}[/bold yellow]")
    
    if not missing_urls:
        console.print("[green]✅ All developers are already in MongoDB![/green]")
        return []
    
    # Confirm with user
    console.print(f"\n   Press Enter to start scraping {len(missing_urls)} missing developers...")
    input()
    
    # Initialize scraper
    await scraper.initialize()
    
    scraped_developers = []
    failed_urls = []
    
    try:
        for i, url in enumerate(missing_urls):
            logger.info(f"[{i+1}/{len(missing_urls)}] Scraping: {url}")
            
            dev_data = await scraper.scrape_developer_detail(url)
            
            if dev_data:
                scraped_developers.append(dev_data)
                logger.info(f"   ✅ {dev_data.get('dev_name', 'Unknown')}")
                
                # Save to MongoDB immediately
                try:
                    result = db_client.upsert_developer(dev_data)
                    if result:
                        logger.info(f"   💾 Saved to MongoDB")
                except Exception as e:
                    logger.error(f"   MongoDB error: {e}")
            else:
                logger.warning(f"   ❌ Failed to scrape")
                failed_urls.append(url)
            
            # Update progress
            scraper._save_progress({
                'developer_urls': developer_urls,
                'last_scraped_index': developer_urls.index(url) + 1 if url in developer_urls else i + 1,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Random delay
            await scraper.random_delay()
        
        logger.info(f"\n🎉 Scraped {len(scraped_developers)} developers!")
        
        if failed_urls:
            logger.warning(f"⚠️ Failed to scrape {len(failed_urls)} URLs")
            with open('failed_developer_urls.json', 'w', encoding='utf-8') as f:
                json.dump(failed_urls, f, ensure_ascii=False, indent=2)
            logger.info("   Saved failed URLs to failed_developer_urls.json")
        
    except KeyboardInterrupt:
        logger.warning(f"\n⚠️ Interrupted! Scraped {len(scraped_developers)} developers.")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await scraper.close()
    
    return scraped_developers


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Developer Scraper')
    parser.add_argument('--clear', action='store_true', help='Clear all developers from MongoDB before scraping')
    args = parser.parse_args()
    
    console.print("\n" + "=" * 60)
    console.print("[bold blue]    NAWY.COM - SMART DEVELOPER SCRAPER[/bold blue]")
    console.print("[bold blue]    Scrapes ONLY missing developers from MongoDB[/bold blue]")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    stats = db_client.get_collection_stats()
    console.print(f"   Existing: {stats.get('developers', 0)} developers in MongoDB")
    
    # Clear if requested
    if args.clear:
        console.print("\n[bold yellow]🗑️ Clearing all developers from MongoDB...[/bold yellow]")
        try:
            result = db_client._db['developers'].delete_many({})
            console.print(f"   Deleted {result.deleted_count} developers")
        except Exception as e:
            console.print(f"[red]Error clearing: {e}[/red]")
    
    try:
        # Scrape missing developers
        developers = asyncio.run(scrape_missing_developers())
        
        if developers:
            console.print(f"\n[bold green]🎉 Done! Scraped {len(developers)} developers[/bold green]")
        
        # Show final stats
        stats = db_client.get_collection_stats()
        console.print(f"\n[bold]Final count: {stats.get('developers', 0)} developers in MongoDB[/bold]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
