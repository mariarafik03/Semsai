"""
Smart Compound Scraper
======================

This script scrapes ONLY the compounds that are NOT in MongoDB.
It's the most reliable way to get all compounds without duplicates or gaps.

Usage:
    python scrape_smart.py
"""

import asyncio
import json
import sys
import os
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from scrapers.compound_scraper import CompoundScraper
from database.connection import db_client
from utils.data_cleaner import DataCleaner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('scraper_smart.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)

# Progress file for URLs
PROGRESS_FILE = "scraping_progress.json"


def get_existing_nawy_ids():
    """Get all nawy_ids that are already in MongoDB."""
    try:
        compounds_col = db_client._db['compounds']
        existing = compounds_col.find({}, {'nawy_id': 1, 'nawy_url': 1})
        
        # Get both nawy_id and nawy_url to match against
        existing_ids = set()
        existing_urls = set()
        
        for doc in existing:
            if doc.get('nawy_id'):
                existing_ids.add(str(doc['nawy_id']))
            if doc.get('nawy_url'):
                existing_urls.add(doc['nawy_url'])
        
        return existing_ids, existing_urls
    except Exception as e:
        logger.error(f"Error getting existing compounds: {e}")
        return set(), set()


def extract_nawy_id_from_url(url):
    """Extract nawy_id from URL like /compound/123-name"""
    try:
        slug = url.split('/compound/')[-1]
        nawy_id = slug.split('-')[0]
        return nawy_id
    except:
        return None


async def scrape_missing_from_mongodb():
    """Scrape only compounds that are not in MongoDB."""
    
    console.print("\n[bold cyan]🧠 Smart Scraper - Checking MongoDB for missing compounds...[/bold cyan]")
    
    # Load URLs from progress file
    if not os.path.exists(PROGRESS_FILE):
        console.print("[red]❌ Progress file not found! Run main scraper first to get URLs.[/red]")
        return []
    
    with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
        progress = json.load(f)
    
    all_urls = progress.get('compound_urls', [])
    console.print(f"   Total URLs in progress file: {len(all_urls)}")
    
    # Get existing compounds from MongoDB
    existing_ids, existing_urls = get_existing_nawy_ids()
    console.print(f"   Existing in MongoDB: {len(existing_urls)} compounds")
    
    # Find missing URLs
    missing_urls = []
    for url in all_urls:
        # Check by URL
        if url in existing_urls:
            continue
        
        # Check by nawy_id
        nawy_id = extract_nawy_id_from_url(url)
        if nawy_id and nawy_id in existing_ids:
            continue
        
        missing_urls.append(url)
    
    console.print(f"   [bold yellow]Missing compounds to scrape: {len(missing_urls)}[/bold yellow]")
    
    if not missing_urls:
        console.print("[green]✅ All compounds are already in MongoDB![/green]")
        return []
    
    # Confirm with user
    console.print(f"\n   Press Enter to start scraping {len(missing_urls)} missing compounds...")
    input()
    
    # Initialize scraper
    scraper = CompoundScraper()
    await scraper.initialize()
    
    scraped_compounds = []
    failed_urls = []
    
    try:
        for i, url in enumerate(missing_urls):
            logger.info(f"[{i+1}/{len(missing_urls)}] Scraping: {url}")
            
            compound_data = await scraper._scrape_compound_detail(url)
            
            if compound_data:
                # Clean data
                compound_data = DataCleaner.clean_compound(compound_data)
                scraped_compounds.append(compound_data)
                logger.info(f"   ✅ {compound_data.get('name', 'Unknown')}")
                
                # Save to MongoDB immediately
                try:
                    db_client.upsert_compound(compound_data)
                    logger.info(f"   💾 Saved to MongoDB")
                except Exception as e:
                    logger.error(f"   MongoDB error: {e}")
            else:
                logger.warning(f"   ❌ Failed to scrape")
                failed_urls.append(url)
            
            # Random delay
            await scraper.random_delay()
        
        logger.info(f"\n🎉 Scraped {len(scraped_compounds)} missing compounds!")
        
        if failed_urls:
            logger.warning(f"⚠️ Failed to scrape {len(failed_urls)} URLs:")
            for url in failed_urls[:10]:
                logger.warning(f"   - {url}")
            if len(failed_urls) > 10:
                logger.warning(f"   ... and {len(failed_urls) - 10} more")
                
            # Save failed URLs for retry
            with open('failed_urls.json', 'w', encoding='utf-8') as f:
                json.dump(failed_urls, f, ensure_ascii=False, indent=2)
            logger.info("   Saved failed URLs to failed_urls.json")
        
    except KeyboardInterrupt:
        logger.warning(f"\n⚠️ Interrupted! Scraped {len(scraped_compounds)} compounds.")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await scraper.close()
    
    return scraped_compounds


def main():
    console.print("\n" + "=" * 60)
    console.print("[bold blue]    NAWY.COM - SMART COMPOUND SCRAPER[/bold blue]")
    console.print("[bold blue]    Scrapes ONLY missing compounds from MongoDB[/bold blue]")
    console.print("=" * 60 + "\n")
    
    # Connect to MongoDB
    console.print("[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    stats = db_client.get_collection_stats()
    console.print(f"   Existing: {stats['compounds']} compounds in MongoDB")
    
    try:
        # Scrape missing compounds
        compounds = asyncio.run(scrape_missing_from_mongodb())
        
        if compounds:
            console.print(f"\n[bold green]🎉 Done! Scraped {len(compounds)} missing compounds[/bold green]")
        else:
            console.print("[green]✅ All compounds already exist in MongoDB![/green]")
        
        # Show final stats
        stats = db_client.get_collection_stats()
        console.print(f"\n[bold]Final count: {stats['compounds']} compounds in MongoDB[/bold]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
