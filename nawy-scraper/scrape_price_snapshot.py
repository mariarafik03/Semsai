"""
NAWY Price Snapshot Scraper
━━━━━━━━━━━━━━━━━━━━━━━━━━
Weekly scraper that captures property price snapshots from Nawy.com
and stores them in MongoDB for historical trend analysis.

Usage:
    python scrape_price_snapshot.py              # Full run (100 pages)
    python scrape_price_snapshot.py --pages 50   # Custom page count
    python scrape_price_snapshot.py --dry-run    # Test without saving

Designed to run via GitHub Actions cron every Monday at 3 AM UTC.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Set

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.table import Table
from config.settings import settings
from database.connection import db_client
from scrapers.base_scraper import BaseScraper

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    handlers=[
        logging.FileHandler('price_snapshot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class PriceSnapshotScraper(BaseScraper):
    """
    Lightweight scraper that captures price snapshots from Nawy search pages.
    
    Unlike the full unit scraper, this only collects pricing data and metadata
    needed for trend analysis. Runs much faster (~15-30 min vs hours).
    """

    def __init__(self, snapshot_date: datetime = None):
        super().__init__()
        self.snapshot_date = snapshot_date or datetime.now(timezone.utc)
        # ISO week format: "2026-W18"
        self.snapshot_week = self.snapshot_date.strftime('%G-W%V')
        self.stats = {
            'pages_processed': 0,
            'units_found': 0,
            'units_saved': 0,
            'units_skipped_no_price': 0,
            'units_failed': 0,
        }

    async def scrape_search_page(self, page_num: int) -> List[Dict]:
        """
        Scrape a single search page and extract price data.
        Uses __NEXT_DATA__ JSON for reliable data extraction.
        """
        url = f"{settings.base_url}/search?page_number={page_num}&category=property"

        if not await self.safe_goto(url):
            return []

        await asyncio.sleep(2)

        # Try __NEXT_DATA__ first (most reliable)
        next_data = await self.extract_next_data()
        if next_data:
            return self._extract_prices_from_next_data(next_data)

        logger.warning(f"No __NEXT_DATA__ on page {page_num}, skipping")
        return []

    def _extract_prices_from_next_data(self, next_data: Dict) -> List[Dict]:
        """
        Extract price snapshot data from __NEXT_DATA__ JSON.
        Only keeps fields needed for trend analysis (lightweight).
        """
        snapshots = []

        try:
            page_props = next_data.get('props', {}).get('pageProps', {})

            # Get search results
            search_results = page_props.get('loadedSearchResultsSSR', {})
            if isinstance(search_results, dict):
                properties = search_results.get('results', [])
            else:
                properties = search_results or []

            # Fallback locations
            if not properties:
                properties = (
                    page_props.get('properties') or
                    page_props.get('searchResults') or
                    page_props.get('results') or
                    []
                )

            for prop in properties:
                if not isinstance(prop, dict):
                    continue

                # ── Extract price (required field) ──
                price = prop.get('price') or prop.get('cash_price')
                if not price or not isinstance(price, (int, float)) or price <= 0:
                    self.stats['units_skipped_no_price'] += 1
                    continue

                # ── Extract area ──
                area = prop.get('area') or prop.get('built_up_area')
                if isinstance(area, (int, float)) and area > 0:
                    price_per_sqm = round(price / area, 2)
                else:
                    area = None
                    price_per_sqm = None

                # ── Extract compound info ──
                compound = prop.get('compound', {}) or {}
                developer = prop.get('developer', {}) or compound.get('developer', {}) or {}

                # ── Extract property type ──
                prop_type = prop.get('type', {})
                if isinstance(prop_type, dict):
                    property_type = prop_type.get('name', '')
                else:
                    property_type = prop.get('property_type') or str(prop_type) if prop_type else ''

                # ── Extract location ──
                area_obj = prop.get('area_obj', {}) or {}
                location = (
                    prop.get('area_name') or
                    area_obj.get('name') or
                    compound.get('area_name', '')
                )

                # ── Extract payment plan ──
                down_payment = prop.get('down_payment')
                monthly_installment = prop.get('monthly_installment')
                installment_years = prop.get('installment_years')

                # ── Build snapshot document ──
                snapshot = {
                    # Timing
                    'snapshot_date': self.snapshot_date,
                    'snapshot_week': self.snapshot_week,

                    # Identifiers
                    'nawy_id': str(prop.get('id', '')),
                    'compound_name': compound.get('name', ''),
                    'compound_nawy_id': str(compound.get('id', '')) if compound.get('id') else '',
                    'developer_name': developer.get('name', ''),
                    'location': location,

                    # Property info
                    'property_type': property_type,
                    'area': area,
                    'bedrooms': prop.get('bedrooms'),
                    'bathrooms': prop.get('bathrooms'),
                    'finishing': prop.get('finishing') or prop.get('finishing_type'),
                    'sale_type': prop.get('sale_type') or 'Primary',
                    'delivery_year': prop.get('delivery_year'),

                    # ── Price data (core) ──
                    'price': price,
                    'price_per_sqm': price_per_sqm,

                    # Payment plan
                    'down_payment': down_payment,
                    'monthly_installment': monthly_installment,
                    'installment_years': installment_years,
                }

                # Clean None values
                snapshot = {k: v for k, v in snapshot.items() if v is not None and v != ''}

                snapshots.append(snapshot)

        except Exception as e:
            logger.error(f"Error extracting prices: {e}")

        return snapshots

    def save_snapshots(self, snapshots: List[Dict]) -> int:
        """
        Save price snapshots to MongoDB collection 'price_snapshots'.
        Uses insert_many for efficiency (append-only, no upsert).
        """
        if not snapshots:
            return 0

        try:
            result = db_client.db.price_snapshots.insert_many(snapshots, ordered=False)
            saved = len(result.inserted_ids)
            logger.info(f"   💾 Saved {saved} snapshots")
            return saved
        except Exception as e:
            logger.error(f"   ❌ DB error: {e}")
            return 0

    def ensure_indexes(self):
        """Create MongoDB indexes for efficient trend queries."""
        collection = db_client.db.price_snapshots

        collection.create_index([('compound_name', 1), ('snapshot_date', 1)])
        collection.create_index([('location', 1), ('snapshot_date', 1)])
        collection.create_index([('property_type', 1), ('location', 1), ('snapshot_date', 1)])
        collection.create_index([('snapshot_week', 1)])
        collection.create_index([('nawy_id', 1), ('snapshot_week', 1)])

        logger.info("📇 Indexes created/verified")

    def check_already_scraped(self) -> bool:
        """Check if we already have data for this week."""
        existing = db_client.db.price_snapshots.count_documents({
            'snapshot_week': self.snapshot_week
        })
        return existing > 0


async def main():
    parser = argparse.ArgumentParser(description='Nawy Price Snapshot Scraper')
    parser.add_argument('--pages', type=int, default=100,
                        help='Number of search pages to scrape (default: 100)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')
    parser.add_argument('--force', action='store_true',
                        help='Force run even if this week was already scraped')
    args = parser.parse_args()

    console.print("\n" + "━" * 60)
    console.print("  📊 NAWY PRICE SNAPSHOT SCRAPER")
    console.print("  Weekly price tracking for trend analysis")
    console.print("━" * 60)

    scraper = PriceSnapshotScraper()

    console.print(f"\n  📅 Snapshot Date: {scraper.snapshot_date.strftime('%Y-%m-%d %H:%M UTC')}")
    console.print(f"  📆 Week: {scraper.snapshot_week}")
    console.print(f"  📄 Pages to scrape: {args.pages}")
    console.print(f"  💾 Dry run: {'Yes' if args.dry_run else 'No'}")

    # Connect to MongoDB
    if not args.dry_run:
        console.print("\n  🔌 Connecting to MongoDB...")
        if not db_client.connect():
            console.print("  [red]❌ Failed to connect to MongoDB[/red]")
            return

        # Check if already scraped this week
        if not args.force and scraper.check_already_scraped():
            console.print(f"  [yellow]⚠️  Week {scraper.snapshot_week} already scraped![/yellow]")
            console.print("  Use --force to scrape again.")
            db_client.disconnect()
            return

        # Create indexes
        scraper.ensure_indexes()

        existing_count = db_client.db.price_snapshots.count_documents({})
        console.print(f"  📊 Existing snapshots in DB: {existing_count:,}")

    console.print("\n  🚀 Starting scraper...\n")

    await scraper.initialize()

    try:
        all_snapshots = []
        consecutive_empty = 0

        for page in range(1, args.pages + 1):
            console.print(f"  [cyan]📄 Page {page}/{args.pages}[/cyan]", end="")

            snapshots = await scraper.scrape_search_page(page)

            if not snapshots:
                consecutive_empty += 1
                console.print(f"  [yellow]  → Empty ({consecutive_empty}/5)[/yellow]")
                if consecutive_empty >= 5:
                    console.print("  [red]  5 consecutive empty pages — stopping[/red]")
                    break
            else:
                consecutive_empty = 0
                scraper.stats['units_found'] += len(snapshots)
                console.print(f"  [green]  → {len(snapshots)} units[/green]")
                all_snapshots.extend(snapshots)

            scraper.stats['pages_processed'] += 1

            # Save in batches of 500
            if not args.dry_run and len(all_snapshots) >= 500:
                saved = scraper.save_snapshots(all_snapshots)
                scraper.stats['units_saved'] += saved
                all_snapshots = []

            # Restart browser every 50 pages to free memory
            if page % 50 == 0 and page < args.pages:
                console.print("  [yellow]♻️  Restarting browser...[/yellow]")
                await scraper.close()
                await scraper.initialize()

            # Small delay between pages
            await asyncio.sleep(0.5)

        # Save remaining snapshots
        if not args.dry_run and all_snapshots:
            saved = scraper.save_snapshots(all_snapshots)
            scraper.stats['units_saved'] += saved

    except KeyboardInterrupt:
        console.print("\n  [yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n  [red]❌ Error: {e}[/red]")
        logger.exception("Scraper error")
    finally:
        await scraper.close()
        if not args.dry_run:
            db_client.disconnect()

    # ── Print Results ──
    console.print("\n" + "━" * 60)
    console.print("  📊 SNAPSHOT RESULTS")
    console.print("━" * 60)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Week", scraper.snapshot_week)
    table.add_row("Pages processed", str(scraper.stats['pages_processed']))
    table.add_row("Units found", str(scraper.stats['units_found']))
    table.add_row("Units saved", str(scraper.stats['units_saved']))
    table.add_row("Skipped (no price)", str(scraper.stats['units_skipped_no_price']))
    table.add_row("Failed", str(scraper.stats['units_failed']))

    console.print(table)
    console.print()

    # Show sample data
    if args.dry_run and all_snapshots:
        console.print("  [yellow]📋 Sample snapshot (dry run):[/yellow]")
        sample = all_snapshots[0]
        for k, v in sample.items():
            if k != 'snapshot_date':
                console.print(f"    {k}: {v}")


if __name__ == '__main__':
    asyncio.run(main())
