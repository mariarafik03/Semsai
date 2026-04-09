"""
Scrape Missing Compounds Script
===============================

This script scrapes compounds that were missed during the main scrape.
It reads the missing URL indices and scrapes only those.

Usage:
    python scrape_missing.py
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
from scrapers.compound_scraper import CompoundScraper
from database.connection import db_client
from utils.data_cleaner import DataCleaner
from utils.export import Exporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('scraper_missing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)

# Missing compound ranges - these are the compounds that were skipped
# Range 1: 279-489 (first gap - scraper stopped at 409, resumed from old progress)
# Range 2: 766-1094 (second gap - scraper stopped at 766, resumed at 1094)
# Range 3: 1174-1300 (third gap - scraper stopped, resumed later)
MISSING_RANGES = [
    (279, 489),    # ~210 compounds
    (766, 1094),   # ~328 compounds
    (1174, 1300),  # ~126 compounds
]


async def scrape_missing_compounds():
    """Scrape the missing compounds from the defined ranges."""
    
    console.print("\n[bold cyan]🔄 Scraping Missing Compounds...[/bold cyan]")
    
    # Load the progress file to get all URLs
    progress_file = "scraping_progress.json"
    if not os.path.exists(progress_file):
        console.print("[red]❌ Progress file not found![/red]")
        return []
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        progress = json.load(f)
    
    all_urls = progress.get('compound_urls', [])
    
    console.print(f"   Total URLs in progress file: {len(all_urls)}")
    
    # Collect all missing URLs from all ranges
    missing_urls_with_indices = []
    for start_idx, end_idx in MISSING_RANGES:
        for i in range(start_idx, min(end_idx, len(all_urls))):
            missing_urls_with_indices.append((i, all_urls[i]))
        console.print(f"   Range {start_idx}-{end_idx}: {min(end_idx, len(all_urls)) - start_idx} compounds")
    
    console.print(f"   [bold]Total missing to scrape: {len(missing_urls_with_indices)}[/bold]")
    
    if not missing_urls_with_indices:
        console.print("[yellow]⚠️ No missing URLs to scrape[/yellow]")
        return []
    
    # Initialize scraper
    scraper = CompoundScraper()
    await scraper.initialize()
    
    scraped_compounds = []
    
    try:
        for i, (actual_index, url) in enumerate(missing_urls_with_indices):
            logger.info(f"[{i+1}/{len(missing_urls_with_indices)}] (index {actual_index}) Scraping: {url}")
            
            compound_data = await scraper._scrape_compound_detail(url)
            
            if compound_data:
                scraped_compounds.append(compound_data)
                logger.info(f"   ✅ {compound_data.get('name', 'Unknown')}")
                
                # Save to MongoDB immediately
                try:
                    if db_client._db is not None:
                        db_client.upsert_compound(compound_data)
                        logger.info(f"   💾 Saved to MongoDB")
                except Exception as e:
                    logger.debug(f"   MongoDB save error: {e}")
            else:
                logger.warning(f"   ❌ Failed to scrape")
            
            # Random delay
            await scraper.random_delay()
        
        logger.info(f"\n🎉 Scraped {len(scraped_compounds)} missing compounds!")
        
    finally:
        await scraper.close()
    
    return scraped_compounds


def main():
    console.print("\n[bold blue]=" * 60 + "[/bold blue]")
    console.print("[bold blue]    NAWY.COM - SCRAPE MISSING COMPOUNDS[/bold blue]")
    console.print("[bold blue]=" * 60 + "[/bold blue]\n")
    
    # Connect to MongoDB
    console.print("[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    stats = db_client.get_collection_stats()
    console.print(f"   Existing: {stats['compounds']} compounds")
    
    try:
        # Scrape missing compounds
        compounds = asyncio.run(scrape_missing_compounds())
        
        if compounds:
            # Clean data
            compounds = [DataCleaner.clean_compound(c) for c in compounds]
            
            # Save to MongoDB
            console.print(f"\n[bold cyan]💾 Saving {len(compounds)} missing compounds to MongoDB...[/bold cyan]")
            result = db_client.bulk_upsert_compounds(compounds)
            console.print(f"   Inserted: {result['inserted']}, Updated: {result['updated']}")
            
            # Export
            console.print("\n[bold cyan]📁 Exporting...[/bold cyan]")
            exporter = Exporter()
            paths = exporter.export_all(compounds, [], [], 'both')
            for name, path in paths.items():
                console.print(f"   {name}: {path}")
            
            console.print(f"\n[bold green]🎉 Done! Scraped {len(compounds)} missing compounds[/bold green]")
        else:
            console.print("[yellow]⚠️ No compounds scraped[/yellow]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.exception("Error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
