"""
NAWY Search Page Unit Scraper - FULL DATA
Uses search page pagination to get URLs, then visits each unit page
to extract COMPLETE data (same as compound scraper).

Target: ~20,316 units with FULL data schema
"""

import os
import sys
import json
import asyncio
import logging
import traceback
import re
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

# Import the compound scraper's class to use its scrape_unit_detail method
from scrape_units_compound import CompoundUnitScraper

console = Console()
logger = logging.getLogger(__name__)

PROGRESS_FILE = 'units_search_full_progress.json'


class SearchFullScraper(CompoundUnitScraper):
    """
    Uses search page to discover units, then scrapes full details
    using the same method as CompoundUnitScraper.
    """
    
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
    
    async def get_unit_urls_from_search_page(self, page_num: int) -> List[Dict]:
        """Get unit URLs and metadata from a search results page."""
        url = f"{settings.base_url}/search?page_number={page_num}&category=property"
        
        if not await self.safe_goto(url):
            return []
        
        await asyncio.sleep(2)
        
        units_metadata = []
        
        # Get __NEXT_DATA__
        next_data = await self.extract_next_data()
        if next_data:
            page_props = next_data.get('props', {}).get('pageProps', {})
            search_results = page_props.get('loadedSearchResultsSSR', {})
            properties = search_results.get('results', []) if isinstance(search_results, dict) else []
            
            for prop in properties:
                if isinstance(prop, dict):
                    prop_id = prop.get('id')
                    if not prop_id:
                        continue
                    
                    # Build URL
                    compound = prop.get('compound', {}) or {}
                    compound_id = compound.get('id', '')
                    compound_slug = compound.get('slug', 'compound')
                    slug = prop.get('slug', '')
                    
                    if slug:
                        full_url = f"{settings.base_url}/compound/{compound_id}-{compound_slug}/property/{slug}"
                    else:
                        full_url = f"{settings.base_url}/compound/{compound_id}-{compound_slug}/property/{prop_id}"
                    
                    # Get developer info
                    developer = prop.get('developer', {})
                    dev_info = {}
                    if developer:
                         dev_info = {
                             'developer_name': developer.get('name'),
                             'developer_id': str(developer.get('id', ''))
                         }
                    
                    units_metadata.append({
                        'url': full_url,
                        'nawy_id': str(prop_id),
                        'compound_info': dev_info  # Helper for scrape_unit_detail
                    })
        
        return units_metadata


def get_existing_unit_urls() -> Set[str]:
    """Get all existing unit URLs from database."""
    existing = set()
    for unit in db_client.db.units.find({}, {'nawy_url': 1, 'nawy_id': 1}):
        if unit.get('nawy_url'):
            existing.add(unit['nawy_url'])
        # Also track by nawy_id
        if unit.get('nawy_id'):
            existing.add(str(unit['nawy_id']))
    return existing


async def main():
    console.print("\n" + "=" * 60)
    console.print("    [bold cyan]NAWY.COM - SEARCH PAGE FULL SCRAPER[/bold cyan]")
    console.print("    Scrapes ALL units with COMPLETE data (~20,316)")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("Connecting to MongoDB...")
    db_client.connect()
    
    existing = get_existing_unit_urls()
    console.print(f"   Existing units in MongoDB: {len(existing)}")
    
    # Load progress
    scraper = SearchFullScraper()
    progress = scraper._load_progress()
    start_page = progress['last_page'] + 1
    stats = progress['stats']
    
    # Estimate pages needed (~12-21 units per page, ~20k total = ~1000-1700 pages)
    TOTAL_PAGES = 1700  # Buffer
    
    console.print(f"   Estimated pages: ~{TOTAL_PAGES}")
    console.print(f"   [green]📂 Resuming from page {start_page}[/green]")
    
    input("\n   Press Enter to start...")
    
    await scraper.initialize()
    
    try:
        page = start_page
        consecutive_empty = 0
        
        while page <= TOTAL_PAGES:
            console.print(f"\n[cyan]📄 Page {page}/{TOTAL_PAGES}[/cyan]")
            
            # Get unit URLs from search page
            urls = await scraper.get_unit_urls_from_search_page(page)
            
            if not urls:
                consecutive_empty += 1
                console.print(f"   [yellow]Empty page ({consecutive_empty}/5)[/yellow]")
                if consecutive_empty >= 5:
                    console.print("   [red]5 consecutive empty pages - stopping[/red]")
                    break
                page += 1
                continue
            else:
                consecutive_empty = 0
                stats['units_found'] += len(urls)
                console.print(f"   [green]Found {len(urls)} unit URLs[/green]")
            
            # Process each unit
            page_scraped = 0
            page_skipped = 0
            
            # Process each unit
            page_scraped = 0
            page_skipped = 0
            
            for unit_item in urls:  # 'urls' is now a list of dicts
                if isinstance(unit_item, dict):
                    url = unit_item.get('url')
                    compound_info = unit_item.get('compound_info', {})
                    nawy_id = unit_item.get('nawy_id', '')
                else:
                    # Fallback for old behaviour (just strings)
                    url = unit_item
                    compound_info = {}
                    nawy_id = ''
                
                if not url:
                    continue

                # Extract nawy_id from URL if missing
                if not nawy_id:
                    id_match = re.search(r'/property/(\d+)', url)
                    nawy_id = id_match.group(1) if id_match else ''
                
                # Skip if already exists
                if url in existing or nawy_id in existing:
                    stats['units_skipped'] += 1
                    page_skipped += 1
                    continue
                
                # Scrape full unit details using compound scraper's method
                # Pass compound_info (contains developer info)
                unit_data = await scraper.scrape_unit_detail(url, compound_info=compound_info)
                
                if unit_data:
                    # Insert to database
                    try:
                        db_client.db.units.update_one(
                            {'nawy_id': unit_data.get('nawy_id', nawy_id)},
                            {'$set': unit_data},
                            upsert=True
                        )
                        stats['units_scraped'] += 1
                        page_scraped += 1
                        existing.add(url)
                        if nawy_id:
                            existing.add(nawy_id)
                        console.print(f"   [green]✅ {unit_data.get('name', 'Unit')[:50]}[/green]")
                    except Exception as e:
                        console.print(f"   [red]❌ DB error: {e}[/red]")
                        stats['units_failed'] += 1
                else:
                    stats['units_failed'] += 1
            
            console.print(f"   [dim]Page summary: {page_scraped} scraped, {page_skipped} skipped[/dim]")
            stats['pages_processed'] += 1
            
            # Save progress every 5 pages
            if page % 5 == 0:
                scraper._save_progress(page, stats)
                console.print(f"   [dim]💾 Progress saved[/dim]")
                
                # Restart browser every 10 pages to prevent memory leaks/heap growth
                if page % 10 == 0:
                    console.print("[yellow]♻️ Restarting browser to free memory...[/yellow]")
                    await scraper.close()
                    await scraper.initialize()
            
            page += 1
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted! Progress saved.[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error in main loop: {e}[/red]")
        console.print(traceback.format_exc())
    finally:
        scraper._save_progress(page, stats)
        await scraper.close()
        db_client.disconnect()
        
        console.print("\n" + "=" * 60)
        console.print("[bold]📊 SCRAPING COMPLETE[/bold]")
        console.print(f"   Pages processed: {stats['pages_processed']}")
        console.print(f"   Units found: {stats['units_found']}")
        console.print(f"   Units scraped: {stats['units_scraped']}")
        console.print(f"   Units skipped: {stats['units_skipped']}")
        console.print(f"   Units failed: {stats['units_failed']}")


if __name__ == "__main__":
    asyncio.run(main())
