#!/usr/bin/env python3
"""
Full Nawy Scraper - Fast Mode (No Browser Required!)
=====================================================
Uses requests + __NEXT_DATA__ extraction instead of Playwright browser.
10-20x faster and no Chromium download needed.

Usage:
    python scrape_all_fast.py                    # Scrape everything
    python scrape_all_fast.py --mode compounds   # Only compounds
    python scrape_all_fast.py --mode developers  # Only developers  
    python scrape_all_fast.py --mode units       # Only units
    python scrape_all_fast.py --mode enrich      # Enrich existing data
"""

import json
import re
import sys
import os
import time
from curl_cffi import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import db_client
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console(force_terminal=True)

MAX_WORKERS = 5  # Reduced to avoid rate limiting
import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

session = requests.Session(impersonate="chrome124")
session.headers.update(HEADERS)


# ============================================================
#                    UTILITY FUNCTIONS
# ============================================================

def strip_html_tags(text: str) -> str:
    """Remove HTML tags and clean up text."""
    if not text:
        return ''
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', text)
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Decode HTML entities
    clean = clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;', "'").replace('&quot;', '"')
    return clean


def extract_next_data(html: str) -> Optional[dict]:
    """Extract __NEXT_DATA__ JSON from HTML page."""
    pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def fetch_page(url: str, retries: int = 3) -> Optional[str]:
    """Fetch page HTML with retries and random delays."""
    for attempt in range(retries):
        try:
            # Rotate User-Agent
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            time.sleep(random.uniform(1.0, 2.0))  # Slower to avoid blocks
            resp = session.get(url, headers=headers, timeout=25)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429 or resp.status_code == 403:
                wait = 30 * (attempt + 1)
                console.print(f"[yellow]Rate limited ({resp.status_code}), waiting {wait}s...[/]")
                time.sleep(wait)
            else:
                return None
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


# ============================================================
#                  PHASE 1A: COMPOUNDS SCRAPER
# ============================================================

def scrape_compounds():
    """Scrape all compounds from Nawy search pages."""
    console.print("\n[bold cyan]== Phase 1A: Scraping Compounds ==[/]")
    
    compounds_col = db_client._db['compounds']
    all_compounds = []
    page_num = 1
    max_pages = 200  # Safety limit
    
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("{task.completed} compounds found"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Scraping search pages...", total=None)
        
        while page_num <= max_pages:
            url = f"https://www.nawy.com/search?page_number={page_num}"
            html = fetch_page(url)
            
            if not html:
                break
            
            data = extract_next_data(html)
            if not data:
                break
            
            page_props = data.get('props', {}).get('pageProps', {})
            
            # Compounds are in loadedSearchResultsSSR.results
            ssr = page_props.get('loadedSearchResultsSSR', {})
            compounds_data = ssr.get('results', [])
            
            if not compounds_data:
                break
            
            for compound in compounds_data:
                if not isinstance(compound, dict):
                    continue
                
                # Extract coordinates
                coords = compound.get('coordinates') or []
                lat = coords[0] if len(coords) > 0 else None
                lng = coords[1] if len(coords) > 1 else None
                
                compound_doc = {
                    'nawy_id': str(compound.get('id', '')),
                    'name': compound.get('name', ''),
                    'slug': compound.get('slug', ''),
                    'developer_name': compound.get('developerName', ''),
                    'developer_id_nawy': str(compound.get('developerId', '')),
                    'developer_logo_url': compound.get('developerLogoUrl', ''),
                    'area_name': compound.get('areaName', ''),
                    'area_id': str(compound.get('areaId', '')),
                    'parent_area_id': str(compound.get('parentAreaId', '')),
                    'property_types': compound.get('propertyTypes', []),
                    'has_offer': compound.get('hasOffer', False),
                    'image_url': compound.get('imageUrl', ''),
                    'lat': lat,
                    'lng': lng,
                    'nawy_url': f"https://www.nawy.com/compound/{compound.get('slug', '')}",
                    'scraped_at': datetime.now(timezone.utc),
                }
                all_compounds.append(compound_doc)
            
            progress.update(task, completed=len(all_compounds))
            page_num += 1
            time.sleep(0.3)  # Small delay between pages
    
    # Save to MongoDB (with reconnect support)
    if all_compounds:
        # Check which are already saved
        existing_ids = set()
        for c in compounds_col.find({}, {'nawy_id': 1}):
            existing_ids.add(c.get('nawy_id', ''))
        
        to_save = [c for c in all_compounds if c['nawy_id'] not in existing_ids]
        console.print(f"\n[cyan]Already saved: {len(existing_ids)} compounds[/]")
        console.print(f"[cyan]New to save: {len(to_save)} compounds[/]")
        
        saved = 0
        for c in to_save:
            try:
                compounds_col.update_one(
                    {'nawy_id': c['nawy_id']},
                    {'$set': c},
                    upsert=True
                )
                saved += 1
            except Exception as e:
                console.print(f"[yellow]Reconnecting... ({e})[/]")
                time.sleep(2)
                db_client.connect()
                compounds_col = db_client._db['compounds']
                try:
                    compounds_col.update_one(
                        {'nawy_id': c['nawy_id']},
                        {'$set': c},
                        upsert=True
                    )
                    saved += 1
                except Exception:
                    pass
        
        total = compounds_col.count_documents({})
        console.print(f"[green]Saved {saved} new compounds. Total in DB: {total}[/]")
    
    return all_compounds


# ============================================================
#                 PHASE 1B: DEVELOPERS SCRAPER
# ============================================================

def scrape_single_developer(url: str) -> Optional[dict]:
    """Scrape a single developer page."""
    html = fetch_page(url)
    if not html:
        return None
    
    data = extract_next_data(html)
    if not data:
        return None
    
    page_props = data.get('props', {}).get('pageProps', {})
    dev_data = page_props.get('developer', {})
    
    if not dev_data:
        return None
    
    return {
        'nawy_id': str(dev_data.get('id', '')),
        'dev_name': dev_data.get('name', ''),
        'slug': dev_data.get('slug', '') or dev_data.get('slugEn', ''),
        'description': strip_html_tags(dev_data.get('description', '')),
        'logo_url': dev_data.get('logoUrl', '') or dev_data.get('logo', ''),
        'areas': [a.get('name', '') for a in dev_data.get('areas', [])],
        'compounds_count': dev_data.get('compoundsCount', 0) or len(dev_data.get('compounds', [])),
        'compound_names': [c.get('name', '') for c in dev_data.get('compounds', [])],
        'compound_ids': [str(c.get('id', '')) for c in dev_data.get('compounds', [])],
        'nawy_url': url,
        'scraped_at': datetime.now(timezone.utc),
    }


def scrape_developers():
    """Scrape all developers from Nawy."""
    console.print("\n[bold cyan]== Phase 1B: Scraping Developers ==[/]")
    
    developers_col = db_client._db['developers']
    
    # First, get developer list from the developers page
    console.print("[cyan]Fetching developer list...[/]")
    
    all_dev_urls = []
    
    # Try getting developers list from the main page
    html = fetch_page("https://www.nawy.com/developers")
    if html:
        data = extract_next_data(html)
        if data:
            page_props = data.get('props', {}).get('pageProps', {})
            developers_list = page_props.get('developers', [])
            
            for dev in developers_list:
                dev_id = dev.get('id', '')
                dev_slug = dev.get('slug', '') or dev.get('slugEn', '')
                if dev_id:
                    url = f"https://www.nawy.com/developer/{dev_id}-{dev_slug}"
                    all_dev_urls.append(url)
    
    # Also collect developer URLs from compounds already in DB
    compounds = list(db_client._db['compounds'].find(
        {'developer_id_nawy': {'$exists': True}},
        {'developer_id_nawy': 1, 'developer_name': 1}
    ))
    
    existing_ids = set()
    for url in all_dev_urls:
        # Extract ID from URL
        id_match = re.search(r'/developer/(\d+)', url)
        if id_match:
            existing_ids.add(id_match.group(1))
    
    for c in compounds:
        dev_id = c.get('developer_id_nawy', '')
        if dev_id and dev_id not in existing_ids:
            url = f"https://www.nawy.com/developer/{dev_id}"
            all_dev_urls.append(url)
            existing_ids.add(dev_id)
    
    console.print(f"[cyan]Found {len(all_dev_urls)} developer URLs to scrape[/]")
    
    if not all_dev_urls:
        console.print("[yellow]No developer URLs found[/]")
        return []
    
    all_developers = []
    
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Scraping developers...", total=len(all_dev_urls))
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(scrape_single_developer, url): url for url in all_dev_urls}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    all_developers.append(result)
                    # Save immediately
                    developers_col.update_one(
                        {'nawy_id': result['nawy_id']},
                        {'$set': result},
                        upsert=True
                    )
                progress.update(task, advance=1)
    
    console.print(f"[green]Scraped and saved {len(all_developers)} developers[/]")
    return all_developers


# ============================================================
#                    PHASE 2: UNITS SCRAPER
# ============================================================

def scrape_single_unit(url: str) -> Optional[dict]:
    """Scrape a single unit page and extract all data."""
    html = fetch_page(url)
    if not html:
        return None
    
    data = extract_next_data(html)
    if not data:
        return None
    
    page_props = data.get('props', {}).get('pageProps', {})
    prop = page_props.get('property', {})
    
    if not prop:
        return None
    
    # Parse delivery year
    delivery_date = prop.get('deliveryDate')
    delivery_year = None
    if delivery_date:
        if isinstance(delivery_date, int):
            delivery_year = delivery_date
        elif isinstance(delivery_date, str):
            if 'T' in delivery_date or '-' in delivery_date:
                date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', delivery_date)
                if date_match:
                    dt = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)), tzinfo=timezone.utc)
                    if dt < datetime.now(timezone.utc):
                        delivery_year = 'Delivered'
                    else:
                        delivery_year = int(date_match.group(1))
            else:
                year_match = re.search(r'(\d{4})', delivery_date)
                if year_match:
                    delivery_year = int(year_match.group(1))
    
    # Parse payment plans
    payment_plans = None
    raw_plans = prop.get('paymentPlans', [])
    if raw_plans:
        payment_plans = []
        for plan in raw_plans:
            cleaned_plan = {
                'frequency': plan.get('frequency'),
                'years': plan.get('years'),
                'years_remaining': plan.get('yearsRemaining'),
                'installment_type': plan.get('installmentType'),
                'is_cash': plan.get('isCash', False),
                'is_offer': plan.get('isOffer', False),
                'is_nawy_now': plan.get('isNawyNow', False),
                'unit_price': plan.get('unitPrice'),
                'currency': plan.get('currency', 'EGP'),
                'single_installment_amount': plan.get('singleInstallmentAmount'),
                'total_installments_amount': plan.get('totalInstallmentsAmount'),
                'down_payment': plan.get('downPayment'),
                'down_payment_month_1': plan.get('downPaymentMonth1'),
                'down_payment_month_3': plan.get('downPaymentMonth3'),
                'down_payment_month_6': plan.get('downPaymentMonth6'),
                'delivery_payment': plan.get('deliveryPayment'),
                'contractual_payment': plan.get('contractualPayment'),
                'discount_percentage': plan.get('discountPercentage'),
                'discount_value': plan.get('discountValue'),
                'offer_valid_till': plan.get('offerValidTill'),
                'milestones': [
                    {
                        'name': m.get('name'),
                        'total': m.get('total'),
                        'included_in_price': m.get('includedInPrice', False),
                        'frequency': m.get('frequency'),
                        'total_installments_count': m.get('totalInstallmentsCount'),
                        'single_installment_amount': m.get('singleInstallmentAmount'),
                    } for m in plan.get('milestones', [])
                ]
            }
            payment_plans.append(cleaned_plan)
    
    # Get compound info
    compound = prop.get('compound', {}) or {}
    
    unit_doc = {
        'nawy_id': str(prop.get('id', '')),
        'reference_no': str(prop.get('id', '')),
        'name': prop.get('name', ''),
        'slug': prop.get('slug', '') or prop.get('slugEn', ''),
        'description': strip_html_tags(prop.get('description', '')),
        'property_type': prop.get('propertyType', ''),
        'unit_type': prop.get('propertyType', ''),
        'price': prop.get('price') or prop.get('minPrice'),
        'price_min': prop.get('minPrice'),
        'price_max': prop.get('maxPrice'),
        'area': prop.get('minUnitArea') or prop.get('maxUnitArea') or prop.get('unitArea'),
        'area_min': prop.get('minUnitArea'),
        'area_max': prop.get('maxUnitArea'),
        'bedrooms': prop.get('numberOfBedrooms'),
        'bathrooms': prop.get('numberOfBathrooms'),
        'finishing': prop.get('finishing', ''),
        'sale_type': 'Resale' if prop.get('resale') else 'Developer Sale',
        'delivery_year': delivery_year,
        'developer_name': prop.get('developerName', ''),
        'developer_id_nawy': str(prop.get('developerId', '')),
        'compound_name': compound.get('name', ''),
        'compound_nawy_id': str(compound.get('id', '')),
        'location': f"{compound.get('areaName', '')}, {prop.get('areaName', '')}".strip(', '),
        'images': prop.get('images', []),
        'nawy_url': url,
        'payment_plans': payment_plans,
        'scraped_at': datetime.now(timezone.utc),
    }
    
    return unit_doc


def scrape_units():
    """Scrape all units using search?category=property pagination."""
    console.print("\n[bold cyan]== Phase 2: Scraping Units ==[/]")
    
    units_col = db_client._db['units']
    
    # Check which units already exist
    existing_units = set()
    for u in units_col.find({}, {'nawy_id': 1}):
        existing_units.add(u.get('nawy_id', ''))
    console.print(f"[green]Already have {len(existing_units)} units in DB[/]")
    
    # Step 1: Collect all unit URLs from search pages
    console.print("[cyan]Step 1: Collecting unit URLs from search pages...[/]")
    all_unit_urls = []
    page_num = 1
    max_pages = 2000
    
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("{task.completed} units found"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Scanning search pages...", total=None)
        
        while page_num <= max_pages:
            url = f"https://www.nawy.com/search?category=property&page_number={page_num}"
            html = fetch_page(url)
            
            if not html:
                break
            
            data = extract_next_data(html)
            if not data:
                break
            
            page_props = data.get('props', {}).get('pageProps', {})
            ssr = page_props.get('loadedSearchResultsSSR', {})
            results = ssr.get('results', [])
            
            if not results:
                break
            
            for unit in results:
                if not isinstance(unit, dict):
                    continue
                unit_id = str(unit.get('id', ''))
                unit_slug = unit.get('slug', '')
                compound_info = unit.get('compound', {}) or {}
                compound_slug = compound_info.get('slug', '')
                
                if unit_id and unit_id not in existing_units:
                    unit_url = f"https://www.nawy.com/compound/{compound_slug}/property/{unit_slug}"
                    all_unit_urls.append((unit_id, unit_url))
            
            progress.update(task, completed=len(all_unit_urls))
            page_num += 1
            time.sleep(0.2)
    
    console.print(f"[cyan]Found {len(all_unit_urls)} new units to scrape[/]")
    
    if not all_unit_urls:
        console.print("[yellow]No new units to scrape[/]")
        return
    
    # Step 2: Scrape individual unit pages in parallel
    console.print("[cyan]Step 2: Scraping unit details...[/]")
    
    scraped = 0
    errors = 0
    
    # Lookup: compound nawy_id -> ObjectId
    compound_lookup = {}
    for c in db_client._db['compounds'].find({}, {'nawy_id': 1}):
        compound_lookup[str(c.get('nawy_id', ''))] = c['_id']
    
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Scraping unit details...", total=len(all_unit_urls))
        
        # Process in batches of 100 to save progress
        batch_size = 100
        for i in range(0, len(all_unit_urls), batch_size):
            batch = all_unit_urls[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(scrape_single_unit, url): (uid, url) for uid, url in batch}
                
                for future in as_completed(futures):
                    unit = future.result()
                    if unit:
                        # Link compound_id
                        comp_nawy_id = unit.get('compound_nawy_id', '')
                        if comp_nawy_id in compound_lookup:
                            unit['compound_id'] = compound_lookup[comp_nawy_id]
                        
                        try:
                            units_col.update_one(
                                {'nawy_id': unit['nawy_id']},
                                {'$set': unit},
                                upsert=True
                            )
                            scraped += 1
                        except Exception as e:
                            time.sleep(2)
                            db_client.connect()
                            units_col = db_client._db['units']
                            try:
                                units_col.update_one(
                                    {'nawy_id': unit['nawy_id']},
                                    {'$set': unit},
                                    upsert=True
                                )
                                scraped += 1
                            except Exception:
                                errors += 1
                    else:
                        errors += 1
                    
                    progress.update(task, advance=1,
                                  description=f"Scraping unit details... ({scraped} saved)")
    
    total_in_db = units_col.count_documents({})
    console.print(f"\n[green]New units scraped: {scraped}[/]")
    console.print(f"[yellow]Errors/skipped: {errors}[/]")
    console.print(f"[green]Total units in DB: {total_in_db}[/]")


# ============================================================
#                  PHASE 3: LINK & ENRICH
# ============================================================

def link_units_to_developers():
    """Link units to developers using MongoDB ObjectId."""
    console.print("\n[bold cyan]== Phase 3A: Linking Units to Developers ==[/]")
    
    units_col = db_client._db['units']
    developers_col = db_client._db['developers']
    
    # Build lookup: nawy_id -> ObjectId
    dev_lookup = {}
    for dev in developers_col.find({}, {'nawy_id': 1}):
        dev_lookup[str(dev.get('nawy_id', ''))] = dev['_id']
    
    console.print(f"[cyan]Loaded {len(dev_lookup)} developers[/]")
    
    # Update units
    units = list(units_col.find(
        {'developer_id': {'$exists': False}},
        {'_id': 1, 'developer_id_nawy': 1}
    ))
    
    console.print(f"[cyan]Found {len(units)} units to link[/]")
    
    updated = 0
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Linking units...", total=len(units))
        for unit in units:
            dev_nawy_id = str(unit.get('developer_id_nawy', ''))
            if dev_nawy_id in dev_lookup:
                units_col.update_one(
                    {'_id': unit['_id']},
                    {'$set': {'developer_id': dev_lookup[dev_nawy_id]}}
                )
                updated += 1
            progress.update(task, advance=1)
    
    console.print(f"[green]Linked {updated} units to developers[/]")


def link_compounds_to_developers():
    """Link compounds to developers using MongoDB ObjectId."""
    console.print("\n[bold cyan]== Phase 3B: Linking Compounds to Developers ==[/]")
    
    compounds_col = db_client._db['compounds']
    developers_col = db_client._db['developers']
    
    dev_lookup = {}
    for dev in developers_col.find({}, {'nawy_id': 1}):
        dev_lookup[str(dev.get('nawy_id', ''))] = dev['_id']
    
    compounds = list(compounds_col.find(
        {'developer_id': {'$exists': False}},
        {'_id': 1, 'developer_id_nawy': 1}
    ))
    
    console.print(f"[cyan]Found {len(compounds)} compounds to link[/]")
    
    updated = 0
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(), console=console
    ) as progress:
        task = progress.add_task("Linking compounds...", total=len(compounds))
        for c in compounds:
            dev_nawy_id = str(c.get('developer_id_nawy', ''))
            if dev_nawy_id in dev_lookup:
                compounds_col.update_one(
                    {'_id': c['_id']},
                    {'$set': {'developer_id': dev_lookup[dev_nawy_id]}}
                )
                updated += 1
            progress.update(task, advance=1)
    
    console.print(f"[green]Linked {updated} compounds to developers[/]")


# ============================================================
#                      MAIN ENTRY POINT
# ============================================================

def print_stats():
    """Print current database stats."""
    stats = db_client.get_collection_stats()
    table = Table(title="Database Stats")
    table.add_column("Collection", style="cyan")
    table.add_column("Count", style="green", justify="right")
    
    for name, count in stats.items():
        table.add_row(name, str(count))
    
    console.print(table)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Nawy Fast Scraper')
    parser.add_argument('--mode', choices=['all', 'compounds', 'developers', 'units', 'enrich'],
                       default='all', help='Scraping mode')
    args = parser.parse_args()
    
    console.print("[bold blue]========================================[/]")
    console.print("[bold blue]   NAWY FAST SCRAPER (No Browser!)     [/]")
    console.print("[bold blue]========================================[/]\n")
    
    # Connect to MongoDB
    console.print("[cyan]Connecting to MongoDB...[/]")
    if not db_client.connect():
        console.print("[red]Failed to connect to MongoDB![/]")
        return
    
    print_stats()
    
    try:
        if args.mode in ('all', 'compounds'):
            scrape_compounds()
        
        if args.mode in ('all', 'developers'):
            scrape_developers()
        
        if args.mode in ('all', 'units'):
            scrape_units()
        
        if args.mode in ('all', 'enrich'):
            link_units_to_developers()
            link_compounds_to_developers()
        
        console.print("\n[bold green]Done![/]")
        print_stats()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted! Progress is saved - run again to resume.[/]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/]")
        raise
    finally:
        db_client.disconnect()


if __name__ == '__main__':
    main()
