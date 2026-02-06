"""
NAWY Search Page Unit Scraper
Scrapes ALL units from Nawy search page using pagination.
Target: ~20,316 units
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from config.settings import settings
from database.connection import db_client
from scrapers.base_scraper import BaseScraper

console = Console()
logger = logging.getLogger(__name__)

PROGRESS_FILE = 'units_search_progress.json'


class SearchUnitScraper(BaseScraper):
    """Scrapes units from Nawy search page with pagination."""
    
    def __init__(self):
        super().__init__()
        self.scraped_urls: Set[str] = set()
    
    def _load_progress(self) -> Dict:
        """Load progress from file."""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {'last_page': 0, 'stats': {
            'pages_processed': 0,
            'units_found': 0,
            'units_scraped': 0,
            'units_skipped': 0,
            'units_failed': 0
        }}
    
    def _save_progress(self, page: int, stats: Dict):
        """Save progress to file."""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({
                'last_page': page,
                'stats': stats,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
    
    async def get_units_from_search_page(self, page_num: int) -> List[Dict]:
        """Get unit URLs from a search results page."""
        url = f"{settings.base_url}/search?page_number={page_num}&category=property"
        
        if not await self.safe_goto(url):
            return []
        
        await asyncio.sleep(2)
        
        units = []
        
        # Try __NEXT_DATA__ first (fastest and most reliable)
        next_data = await self.extract_next_data()
        if next_data:
            units = self._extract_units_from_search_data(next_data)
        
        if not units:
            # Fallback to HTML parsing
            html = await self.get_page_content()
            units = self._extract_units_from_html(html)
        
        return units
    
    def _extract_units_from_search_data(self, next_data: Dict) -> List[Dict]:
        """Extract COMPLETE unit data from __NEXT_DATA__ JSON."""
        units = []
        
        try:
            page_props = next_data.get('props', {}).get('pageProps', {})
            
            # Try different locations for properties
            # Search page uses loadedSearchResultsSSR.results
            search_results = page_props.get('loadedSearchResultsSSR', {})
            if isinstance(search_results, dict):
                properties = search_results.get('results', [])
            else:
                properties = search_results or []
            
            # Fallback to other possible locations
            if not properties:
                properties = (
                    page_props.get('properties') or
                    page_props.get('searchResults') or
                    page_props.get('data', {}).get('properties') or
                    page_props.get('results') or
                    []
                )
            
            for prop in properties:
                if isinstance(prop, dict):
                    # Build unit info
                    prop_id = prop.get('id')
                    if not prop_id:
                        continue
                    
                    # Build URL
                    prop_url = prop.get('url') or prop.get('property_url')
                    compound = prop.get('compound', {}) or {}
                    compound_id = compound.get('id') or prop.get('compound_id', '')
                    compound_slug = compound.get('slug') or 'compound'
                    
                    if prop_url:
                        full_url = urljoin(settings.base_url, prop_url)
                    else:
                        slug = prop.get('slug') or prop.get('url_slug') or 'property'
                        full_url = f"{settings.base_url}/compound/{compound_id}-{compound_slug}/property/{prop_id}-{slug}"
                    
                    # Get developer info
                    developer = prop.get('developer', {}) or compound.get('developer', {}) or {}
                    
                    # Get property type
                    prop_type = prop.get('type', {})
                    if isinstance(prop_type, dict):
                        property_type = prop_type.get('name', '')
                    else:
                        property_type = prop.get('property_type') or str(prop_type) if prop_type else ''
                    
                    # Get area data
                    area = prop.get('area') or prop.get('built_up_area')
                    area_min = prop.get('minUnitArea') or prop.get('min_area')
                    area_max = prop.get('maxUnitArea') or prop.get('max_area')
                    
                    # Get price data
                    price = prop.get('price') or prop.get('cash_price')
                    price_min = prop.get('minUnitPrice') or prop.get('min_price')
                    price_max = prop.get('maxUnitPrice') or prop.get('max_price')
                    
                    # Get payment plan
                    payment_plan = {}
                    if prop.get('down_payment'):
                        payment_plan['down_payment'] = prop.get('down_payment')
                    if prop.get('monthly_installment'):
                        payment_plan['monthly_installment'] = prop.get('monthly_installment')
                    if prop.get('installment_years'):
                        payment_plan['installment_years'] = prop.get('installment_years')
                    
                    # Get location
                    area_obj = prop.get('area_obj', {}) or {}
                    location = prop.get('area_name') or area_obj.get('name') or compound.get('area_name', '')
                    
                    # Build complete unit matching original schema
                    unit = {
                        'name': prop.get('name') or prop.get('title', ''),
                        'nawy_id': str(prop_id),
                        'nawy_url': full_url,
                        'reference_no': prop.get('reference_no') or prop.get('reference'),
                        'location': location,
                        
                        # Compound info
                        'compound_name': compound.get('name', ''),
                        'compound_nawy_id': str(compound_id) if compound_id else '',
                        
                        # Developer info
                        'developer_name': developer.get('name', ''),
                        'developer_id': str(developer.get('id', '')) if developer.get('id') else '',
                        
                        # Property details
                        'property_type': property_type,
                        'area': area,
                        'area_min': area_min,
                        'area_max': area_max,
                        'price': price,
                        'price_min': price_min,
                        'price_max': price_max,
                        'bedrooms': prop.get('bedrooms'),
                        'bathrooms': prop.get('bathrooms'),
                        'delivery_year': prop.get('delivery_year') or prop.get('delivery_date'),
                        'finishing': prop.get('finishing') or prop.get('finishing_type'),
                        'sale_type': prop.get('sale_type') or 'Primary',
                        
                        # Location coordinates
                        'lat': prop.get('latitude') or prop.get('lat'),
                        'lng': prop.get('longitude') or prop.get('lng'),
                        
                        # Content
                        'description': (prop.get('description') or '')[:2000],
                        'images': prop.get('images') or [],
                        'amenities': prop.get('amenities') or [],
                        
                        # Payment
                        'payment_plan': payment_plan if payment_plan else None,
                        
                        # Metadata
                        'scraped_at': datetime.now().isoformat(),
                    }
                    
                    # Clean None and empty values
                    unit = {k: v for k, v in unit.items() if v is not None and v != '' and v != [] and v != {}}
                    
                    units.append(unit)
                    
        except Exception as e:
            logger.debug(f"Error extracting search data: {e}")
        
        return units
    
    def _extract_units_from_html(self, html: str) -> List[Dict]:
        """Extract unit URLs from HTML as fallback."""
        units = []
        soup = self.parse_html(html)
        
        # Find property links
        links = soup.select('a[href*="/property/"]')
        for link in links:
            href = link.get('href', '')
            if '/property/' in href:
                full_url = urljoin(settings.base_url, href)
                # Extract ID from URL
                import re
                match = re.search(r'/property/(\d+)-', full_url)
                nawy_id = match.group(1) if match else ''
                
                units.append({
                    'url': full_url,
                    'nawy_id': nawy_id
                })
        
        return units
    
    async def scrape_unit_detail(self, url: str, basic_info: Dict = None) -> Optional[Dict]:
        """Scrape detailed data from a unit page."""
        if not await self.safe_goto(url):
            return None
        
        await asyncio.sleep(1.5)
        
        try:
            html = await self.get_page_content()
            soup = self.parse_html(html)
            
            # Get __NEXT_DATA__
            next_data = await self.extract_next_data()
            prop_data = {}
            if next_data:
                page_props = next_data.get('props', {}).get('pageProps', {})
                prop_data = (
                    page_props.get('property') or
                    page_props.get('unit') or
                    page_props.get('data', {}).get('property') or
                    {}
                )
            
            # Get basic fields from prop_data or basic_info
            nawy_id = basic_info.get('nawy_id') if basic_info else ''
            if not nawy_id:
                import re
                match = re.search(r'/property/(\d+)-', url)
                nawy_id = match.group(1) if match else ''
            
            name = prop_data.get('name') or prop_data.get('title') or ''
            if not name:
                h1 = soup.select_one('h1')
                name = h1.get_text(strip=True) if h1 else ''
            
            # Build unit data
            unit_data = {
                'nawy_id': nawy_id,
                'nawy_url': url,
                'name': name,
                'price': prop_data.get('price') or prop_data.get('cash_price'),
                'area': prop_data.get('area') or prop_data.get('built_up_area'),
                'bedrooms': prop_data.get('bedrooms'),
                'bathrooms': prop_data.get('bathrooms'),
                'property_type': prop_data.get('property_type') or prop_data.get('type'),
                'finishing': prop_data.get('finishing') or prop_data.get('finishing_type'),
                'compound_name': prop_data.get('compound', {}).get('name') if isinstance(prop_data.get('compound'), dict) else basic_info.get('compound_name') if basic_info else None,
                'developer_name': prop_data.get('developer', {}).get('name') if isinstance(prop_data.get('developer'), dict) else None,
                'location': prop_data.get('area_name') or prop_data.get('location'),
                'down_payment': prop_data.get('down_payment'),
                'installment_years': prop_data.get('installment_years'),
                'scraped_at': datetime.now().isoformat(),
            }
            
            # Clean None values
            unit_data = {k: v for k, v in unit_data.items() if v is not None}
            
            return unit_data
            
        except Exception as e:
            logger.error(f"Error scraping unit {url}: {e}")
            return None


def get_existing_unit_urls() -> Set[str]:
    """Get all existing unit URLs from database."""
    existing = set()
    for unit in db_client.db.units.find({}, {'nawy_url': 1}):
        if unit.get('nawy_url'):
            existing.add(unit['nawy_url'])
    return existing


async def main():
    console.print("\n" + "=" * 60)
    console.print("    NAWY.COM - SEARCH PAGE UNIT SCRAPER")
    console.print("    Scrapes ALL units from search results (~20,316)")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("Connecting to MongoDB...")
    db_client.connect()
    
    existing_urls = get_existing_unit_urls()
    console.print(f"   Existing units in MongoDB: {len(existing_urls)}")
    
    # Load progress
    scraper = SearchUnitScraper()
    progress = scraper._load_progress()
    start_page = progress['last_page'] + 1
    stats = progress['stats']
    
    # Estimate pages needed (~20 units per page, ~20k total = ~1000 pages)
    UNITS_PER_PAGE = 20
    TOTAL_UNITS = 20316
    TOTAL_PAGES = (TOTAL_UNITS // UNITS_PER_PAGE) + 1
    
    console.print(f"   Estimated pages: {TOTAL_PAGES}")
    console.print(f"   📂 Resuming from page {start_page}")
    
    input("\n   Press Enter to start...")
    
    await scraper.initialize()
    
    try:
        page = start_page
        consecutive_empty = 0
        
        while page <= TOTAL_PAGES + 50:  # Extra buffer
            console.print(f"[cyan]📄 Page {page}/{TOTAL_PAGES}[/cyan]")
            
            # Get units from search page
            units = await scraper.get_units_from_search_page(page)
            
            if not units:
                consecutive_empty += 1
                console.print(f"   [yellow]Empty page ({consecutive_empty}/5)[/yellow]")
                if consecutive_empty >= 5:
                    console.print("   [red]5 consecutive empty pages - stopping[/red]")
                    break
            else:
                consecutive_empty = 0
                stats['units_found'] += len(units)
                console.print(f"   [green]Found {len(units)} units[/green]")
            
            # Process each unit - INSERT DIRECTLY from search data (no need to visit each page!)
            for unit_data in units:
                url = unit_data.get('nawy_url')
                nawy_id = unit_data.get('nawy_id')
                if not url or not nawy_id:
                    continue
                
                # Skip if already exists
                if url in existing_urls or url in scraper.scraped_urls:
                    stats['units_skipped'] += 1
                    continue
                
                # Insert directly to database (already has full data from search page!)
                try:
                    db_client.db.units.update_one(
                        {'nawy_id': nawy_id},
                        {'$set': unit_data},
                        upsert=True
                    )
                    stats['units_scraped'] += 1
                    scraper.scraped_urls.add(url)
                    existing_urls.add(url)
                    console.print(f"   [green]✅ {unit_data.get('name', 'Unit')[:50]}[/green]")
                except Exception as e:
                    console.print(f"   [red]❌ DB error: {e}[/red]")
                    stats['units_failed'] += 1
            
            stats['pages_processed'] += 1
            
            # Save progress every 5 pages
            if page % 5 == 0:
                scraper._save_progress(page, stats)
                
                # Restart browser every 100 pages (less frequent since we're faster now)
                if page % 100 == 0:
                    console.print("[yellow]♻️ Restarting browser to free memory...[/yellow]")
                    await scraper.close()
                    await scraper.initialize()
            
            page += 1
            await asyncio.sleep(0.5)  # Faster since we don't visit each unit page
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted! Progress saved.[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error in main loop: {e}[/red]")
        console.print(traceback.format_exc())
        console.print(f"[red]❌ Error: {e}[/red]")
    finally:
        scraper._save_progress(page, stats)
        await scraper.close()
        db_client.disconnect()
        
        console.print("\n" + "=" * 60)
        console.print("📊 SCRAPING COMPLETE")
        console.print(f"   Pages processed: {stats['pages_processed']}")
        console.print(f"   Units found: {stats['units_found']}")
        console.print(f"   Units scraped: {stats['units_scraped']}")
        console.print(f"   Units skipped: {stats['units_skipped']}")
        console.print(f"   Units failed: {stats['units_failed']}")


if __name__ == "__main__":
    asyncio.run(main())
