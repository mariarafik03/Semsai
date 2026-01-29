"""
Nawy.com Web Scraper - Main Entry Point
=======================================

A production-grade web scraper for Nawy.com real estate data.

Usage:
    python main.py --mode full          # Full scrape (compounds + developers + units)
    python main.py --mode compounds     # Only compounds
    python main.py --mode developers    # Only developers
    python main.py --mode units         # Only units (requires compounds in DB)
    python main.py --test               # Test with 3 compounds
    python main.py --export csv         # Export format (json/csv/both)
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Optional

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config.settings import settings
from database.connection import db_client
from scrapers.compound_scraper import CompoundScraper
from scrapers.developer_scraper import DeveloperScraper
from scrapers.unit_scraper import UnitScraper
from utils.data_cleaner import DataCleaner
from utils.export import Exporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console(force_terminal=True)


def print_banner():
    """Print startup banner."""
    banner = """
========================================================
        NAWY.COM REAL ESTATE SCRAPER
              Production Grade v1.0                        
========================================================
    """
    console.print(banner, style="bold blue")


def print_stats(compounds: list, developers: list, units: list):
    """Print scraping statistics."""
    table = Table(title="📊 Scraping Results")
    table.add_column("Data Type", style="cyan")
    table.add_column("Count", style="green")
    
    table.add_row("Compounds", str(len(compounds)))
    table.add_row("Developers", str(len(developers)))
    table.add_row("Units", str(len(units)))
    
    console.print(table)


async def scrape_compounds(limit: int = None, resume: bool = True) -> list:
    """Scrape compounds from Nawy."""
    console.print("\n[bold cyan]📋 Scraping Compounds...[/bold cyan]")
    
    scraper = CompoundScraper()
    compounds = await scraper.scrape_all_compounds(
        max_compounds=limit,
        resume=resume
    )
    
    # Clean data
    compounds = [DataCleaner.clean_compound(c) for c in compounds]
    
    console.print(f"[green]✅ Scraped {len(compounds)} compounds[/green]")
    return compounds


async def scrape_developers(limit: int = None) -> list:
    """Scrape developers from Nawy."""
    console.print("\n[bold cyan]👷 Scraping Developers...[/bold cyan]")
    
    scraper = DeveloperScraper()
    developers = await scraper.scrape_all_developers(
        max_developers=limit
    )
    
    # Clean data
    developers = [DataCleaner.clean_developer(d) for d in developers]
    
    console.print(f"[green]✅ Scraped {len(developers)} developers[/green]")
    return developers


async def scrape_units(compounds: list = None, limit_per_compound: int = None) -> list:
    """Scrape units from compounds."""
    console.print("\n[bold cyan]🏢 Scraping Units...[/bold cyan]")
    
    # If no compounds provided, get from DB
    if not compounds:
        compounds = db_client.get_compounds({'nawy_url': {'$exists': True}})
        if not compounds:
            console.print("[yellow]⚠️ No compounds found. Run compounds scrape first.[/yellow]")
            return []
    
    scraper = UnitScraper()
    units = await scraper.scrape_units_from_compounds(
        compounds,
        max_per_compound=limit_per_compound
    )
    
    # Clean data
    units = [DataCleaner.clean_unit(u) for u in units]
    
    console.print(f"[green]✅ Scraped {len(units)} units[/green]")
    return units


def save_to_mongodb(compounds: list, developers: list, units: list):
    """Save scraped data to MongoDB."""
    console.print("\n[bold cyan]💾 Saving to MongoDB...[/bold cyan]")
    
    # Connected already in main
    
    # Save compounds
    if compounds:
        result = db_client.bulk_upsert_compounds(compounds)
        console.print(f"   Compounds: {result['inserted']} new, {result['updated']} updated")
    
    # Save developers
    for dev in developers:
        db_client.upsert_developer(dev)
    if developers:
        console.print(f"   Developers: {len(developers)} processed")
    
    # Save units
    if units:
        result = db_client.bulk_upsert_units(units)
        console.print(f"   Units: {result['inserted']} new, {result['updated']} updated")
    
    # Log scrape
    db_client.log_scrape({
        'scraper_type': 'full',
        'compounds_count': len(compounds),
        'developers_count': len(developers),
        'units_count': len(units),
        'status': 'success'
    })
    
    console.print("[green]✅ Data saved to MongoDB[/green]")


def export_data(compounds: list, developers: list, units: list, format: str):
    """Export data to files."""
    console.print(f"\n[bold cyan]📁 Exporting to {format.upper()}...[/bold cyan]")
    
    exporter = Exporter()
    paths = exporter.export_all(compounds, developers, units, format)
    
    for name, path in paths.items():
        console.print(f"   {name}: {path}")
    
    # Create summary report
    report_path = exporter.create_summary_report(compounds, developers, units)
    console.print(f"   Summary: {report_path}")


async def run_full_scrape(limit: int = None, export_format: str = 'both'):
    """Run complete scraping workflow."""
    compounds = []
    developers = []
    units = []
    
    try:
        # 1. Scrape compounds
        compounds = await scrape_compounds(limit)
        
        # 2. Scrape developers
        developers = await scrape_developers(limit)
        
        # 3. Scrape units from scraped compounds
        if compounds:
            units = await scrape_units(compounds, limit_per_compound=50)
        
        # 4. Save to MongoDB
        save_to_mongodb(compounds, developers, units)
        
        # 5. Export
        export_data(compounds, developers, units, export_format)
        
        # Print summary
        print_stats(compounds, developers, units)
        
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        console.print(f"[red]❌ Error: {e}[/red]")
        raise
    
    return compounds, developers, units


@click.command()
@click.option('--mode', type=click.Choice(['full', 'compounds', 'developers', 'units']), 
              default='full', help='Scraping mode')
@click.option('--limit', type=int, default=None, help='Limit number of items')
@click.option('--test', is_flag=True, help='Test mode (scrape only 3 items)')
@click.option('--export', 'export_format', type=click.Choice(['json', 'csv', 'both']), 
              default='both', help='Export format')
@click.option('--headless/--no-headless', default=True, help='Run browser headless')
@click.option('--dry-run', is_flag=True, help='Scrape but do not save to DB')
@click.option('--replace-db', is_flag=True, help='Clear existing compounds before inserting new data')
@click.option('--resume/--no-resume', default=True, help='Resume from last checkpoint (default: True)')
def main(mode: str, limit: int, test: bool, export_format: str, headless: bool, dry_run: bool, replace_db: bool, resume: bool):
    """
    Nawy.com Real Estate Web Scraper
    
    Scrapes compounds, developers, and units from Nawy.com
    and saves to MongoDB with JSON/CSV exports.
    """
    print_banner()
    
    # Override settings
    if not headless:
        settings.headless = False
    
    if test:
        limit = 3
        console.print("[yellow]🧪 Test mode: limiting to 3 items[/yellow]")
    
    # Connect to MongoDB
    console.print("\n[bold]Connecting to MongoDB...[/bold]")
    if not db_client.connect():
        console.print("[red]❌ Failed to connect to MongoDB[/red]")
        return
    
    # Show existing data
    stats = db_client.get_collection_stats()
    console.print(f"   Existing: {stats['compounds']} compounds, {stats['developers']} developers, {stats['units']} units")
    
    try:
        if mode == 'full':
            asyncio.run(run_full_scrape(limit, export_format))
        
        elif mode == 'compounds':
            compounds = asyncio.run(scrape_compounds(limit, resume=resume))
            if not dry_run:
                if replace_db:
                    console.print("\n[bold yellow]🗑️ Clearing existing compounds...[/bold yellow]")
                    deleted = db_client.clear_compounds()
                    console.print(f"   Deleted {deleted} existing compounds")
                db_client.bulk_upsert_compounds(compounds)
            export_data(compounds, [], [], export_format)
        
        elif mode == 'developers':
            developers = asyncio.run(scrape_developers(limit))
            if not dry_run:
                for dev in developers:
                    db_client.upsert_developer(dev)
            export_data([], developers, [], export_format)
        
        elif mode == 'units':
            units = asyncio.run(scrape_units(limit_per_compound=limit or 50))
            if not dry_run:
                db_client.bulk_upsert_units(units)
            export_data([], [], units, export_format)
        
        console.print("\n[bold green]🎉 Scraping completed successfully![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Scraping interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        logger.exception("Fatal error")
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
